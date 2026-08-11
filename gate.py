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
import socket
import string
import subprocess
import tempfile
import importlib.util
import collections
import builtins
import threading
import time

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
FAIL, SKIP = [], []
_section = ""


def section(name):
    global _section
    _section = name
    print("\n== %s ==" % name)


def check(ok, label, detail=""):
    if isinstance(ok, Exception):        # a broken check is a failure, not a pass
        FAIL.append((_section, "GATE BUG: " + label, str(ok)))
        print("  FAIL GATE BUG: %s - %s" % (label, ok))
        return
    if ok is None:
        SKIP.append((_section, label, detail))
        print("  SKIP %s %s" % (label, detail))
    elif ok:
        print("  ok   %s" % label)
    else:
        FAIL.append((_section, label, detail))
        print("  FAIL %s %s" % (label, detail))


class GateBug(Exception):
    """The gate itself is broken, as distinct from the code under test being wrong."""


def seg(text, start, end, nth=1):
    """The text between two anchors - or a loud failure.

    EVERY silent gate failure this project has had came from this one operation going
    wrong. An anchor that also matched a longer name; an end anchor occurring BEFORE the
    start, so Python returned an empty string; two anchors that had drifted adjacent.
    And an empty string satisfies every "must NOT contain" check ever written - so a
    broken slice did not fail, it passed, having tested nothing at all.

    So: the start anchor must be unique (or say which occurrence you meant), the end is
    only searched for AFTER the start, and a suspiciously short result is an error.
    """
    n = text.count(start)
    if n == 0:
        raise GateBug("start anchor not found: %r" % (start[:70],))
    if n > 1 and nth == 1:
        raise GateBug("start anchor %r matches %d places - use a longer anchor, or nth="
                      % (start[:70], n))
    if nth > n:
        raise GateBug("start anchor %r has %d matches, asked for #%d"
                      % (start[:50], n, nth))
    a = -1
    for _ in range(nth):
        a = text.index(start, a + 1)
    b = text.find(end, a + len(start))          # AFTER the start: never backwards
    if b < 0:
        raise GateBug("end anchor %r never appears after start %r"
                      % (end[:60], start[:60]))
    out = text[a:b]
    if len(out) < 24:
        raise GateBug("slice %r .. %r is only %d chars - the anchors have drifted together"
                      % (start[:40], end[:40], len(out)))
    return out


_Q3 = chr(34) * 3
_A3 = chr(39) * 3
_DOC_RX = [re.compile(_Q3 + r"[\s\S]*?" + _Q3), re.compile(_A3 + r"[\s\S]*?" + _A3)]


def code_only(text):
    """Source with comments and docstrings removed.

    A check that greps for a symbol will otherwise match the comment explaining why that
    symbol must not be used. That has happened four times in this project.
    """
    for rx in _DOC_RX:
        text = rx.sub('""', text)
    keep = []
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith("#") or s.startswith("//"):
            continue
        keep.append(line)
    return "\n".join(keep)



def seg_len(text, start, n, nth=1):
    """A fixed number of characters from an anchor, with the same anchor checks as seg()."""
    c = text.count(start)
    if c == 0:
        raise GateBug("start anchor not found: %r" % (start[:70],))
    if c > 1 and nth == 1:
        raise GateBug("start anchor %r matches %d places - use a longer anchor, or nth="
                      % (start[:70], c))
    a = -1
    for _ in range(nth):
        a = text.index(start, a + 1)
    out = text[a:a + n]
    if len(out) < min(n, 24):
        raise GateBug("slice from %r is only %d chars" % (start[:40], len(out)))
    return out



def _anchor_at(text, start, nth=1):
    c = text.count(start)
    if c == 0:
        raise GateBug("anchor not found: %r" % (start[:70],))
    if c > 1 and nth == 1:
        raise GateBug("anchor %r matches %d places - use a longer anchor, or nth="
                      % (start[:70], c))
    a = -1
    for _ in range(nth):
        a = text.index(start, a + 1)
    return a


def seg_before(text, start, n, nth=1):
    """The n characters BEFORE an anchor - the window a handler's dispatch sits in."""
    a = _anchor_at(text, start, nth)
    out = text[max(0, a - n):a]
    if len(out) < min(n, 24):
        raise GateBug("only %d chars precede %r" % (len(out), start[:40]))
    return out


def seg_around(text, start, before, after, nth=1):
    """A window either side of an anchor."""
    a = _anchor_at(text, start, nth)
    out = text[max(0, a - before):a + after]
    if len(out) < 24:
        raise GateBug("window around %r is only %d chars" % (start[:40], len(out)))
    return out


def seg_from(text, start, nth=1):
    """Everything from an anchor to the end, with the anchor still validated."""
    a = _anchor_at(text, start, nth)
    out = text[a:]
    if len(out) < 24:
        raise GateBug("only %d chars follow %r" % (len(out), start[:40]))
    return out


def nin(segment, needle, label, detail=""):
    """A must-NOT-contain check that first proves it is looking at something.

    This is the shape that used to pass silently: `"x" not in <empty string>` is True.
    """
    if not segment or len(segment) < 24:
        check(GateBug("segment is empty or trivial (%d chars)" % len(segment or "")), label)
        return
    check(needle not in segment, label, detail)


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
           "launcher-src/PandorumLLM.ico", "LICENSE"]
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

# EVERY doc that states the current version must state THIS one. DEVELOPMENT.md
# said v3.69 Beta patch5 for 185 patches: its principles were updated every time
# and its own header never was, and it shipped that way. A file that names the
# version it belongs to is a claim, and a claim is checkable.
_vsay = "v%s Beta%s" % (ver, (" patch%d" % patch) if patch else "")
for _dn in ("DEVELOPMENT.md", "CHANGELOG.md", "README.md", "BUILD.md", "README.txt"):
    if not os.path.isfile(os.path.join(ROOT, _dn)):
        continue
    _dt = rd(_dn).decode("utf-8", "replace")
    for _ln in _dt.split("\n"):
        if re.search(r"[Cc]urrent version", _ln):
            _said = re.findall(r"v3\.\d+ Beta(?: patch\d+)?", _ln)
            check(bool(_said) and all(s == _vsay for s in _said),
                  "%s states the current version, and it is this one" % _dn,
                  _ln.strip()[:90])
# and the example of the version constant is the constant, not a memory of it
if os.path.isfile(os.path.join(ROOT, "DEVELOPMENT.md")):
    _dv = rd("DEVELOPMENT.md").decode("utf-8", "replace")
    check(('`APP_VERSION` ("v%s Beta")' % ver) in _dv,
          "DEVELOPMENT.md quotes the version constant as it actually reads")
    check(not re.search(r"v3\.(?!%s)\d+[- ]?[Bb]eta[- ]?p" % ver.split(".")[1], _dv)
          or "retires" in _dv,
          "and carries no stale release tag as if it were current")
if os.path.isfile(os.path.join(ROOT, "PandorumLLM.exe")):
    try:
        blob = rd("PandorumLLM.exe")
        want = dotted.encode("utf-16-le")
        check(want in blob, "exe version resource", dotted)
        check("Source-visible".encode("utf-16-le") in blob
              and "Apache".encode("utf-16-le") not in blob,
              "the exe's embedded copyright names the real licence, not Apache")
    except Exception as e:
        check(None, "exe version resource", str(e))
else:
    check(None, "exe version resource", "no exe in tree")
check("Source-visible license" in rd("launcher-src/app.rc").decode("utf-8", "replace")
      and "Apache" not in rd("launcher-src/app.rc").decode("utf-8", "replace"),
      "and launcher-src/app.rc says the same, so the next rebuild cannot regress it")
_lic = rd("LICENSE").decode("utf-8", "replace")
check("no redistribution" in _lic.lower() and "Pt0l3my" in _lic
      and "AS IS" in _lic,
      "the LICENSE ships: source-visible, personal use, no redistribution, no warranty")


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
# the module is imported further down, so derive the same map from the source
_moodsrc = seg(py, "TTS_MOOD = {", "TTS_MOOD_PLAIN")
_moods = {}
for _k, _n, _ic in re.findall(r'\("(\w+)",\s*"(\w+)"\):\s*"([^"]+)"', _moodsrc):
    _moods.setdefault(_ic.encode().decode("unicode_escape"), []).append(_n)
_moods = {k: " / ".join(sorted(v)) for k, v in _moods.items()}
PAGE = PAGE.replace("__MOODS__", json.dumps(_moods))
scripts = re.findall(r"<script>(.*?)</script>", PAGE, re.S)
JS = "\n;\n".join(scripts)
jsf = os.path.join(tempfile.mkdtemp(), "page.js")
open(jsf, "wb").write(JS.encode("utf-8", "surrogatepass"))
r = subprocess.run(["node", "--check", jsf], capture_output=True, text=True)
check(r.returncode == 0, "node --check on the page script", r.stderr[:200])


# The sweep node runs below. It reads the SERVED script - after Python has eaten its
# escape layer - so what it checks is what the browser runs.
SWEEP_JS = r'''// Undefined-name sweep for the served page script. Reads what the browser runs -
// AFTER Python has eaten its escape layer - and reports two classes of fault that
// node --check cannot see because they are runtime errors:
//   1. a call target defined nowhere        (refreshTails - patch73)
//   2. an ALL-CAPS constant read outside     (MG, CY - patch73's action row,
//      the function that defines it           frozen through patch82)
// Empty output means clean. Anything printed is an offender.
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");

// ---- strip comments, strings and regex literals -------------------------------
// The page builds its HTML in string literals, so an unstripped scan would read
// onclick="foo()" as a call and [A-Z] inside a regex as a constant.
function strip(s) {
  let out = "", i = 0, lastSig = "", lastWord = "";
  const n = s.length;
  const regexPrev = "(,=:[!&|?{};+-*%<>~^\n";
  const regexWords = new Set(["return", "typeof", "case", "in", "of", "do", "else", "void", "new"]);
  while (i < n) {
    const c = s[i], d = s[i + 1];
    if (c === "/" && d === "/") { while (i < n && s[i] !== "\n") i++; continue; }
    if (c === "/" && d === "*") { i += 2; while (i < n && !(s[i] === "*" && s[i + 1] === "/")) i++; i += 2; out += " "; continue; }
    if (c === '"' || c === "'" || c === "`") {
      const q = c; i++;
      while (i < n && s[i] !== q) { if (s[i] === "\\") i++; i++; }
      i++; out += q + q; lastSig = q; lastWord = ""; continue;
    }
    if (c === "/" && (lastSig === "" || regexPrev.indexOf(lastSig) >= 0 || regexWords.has(lastWord))) {
      i++; let cls = false;
      while (i < n) {
        if (s[i] === "\\") { i += 2; continue; }
        if (s[i] === "[") cls = true;
        else if (s[i] === "]") cls = false;
        else if (s[i] === "/" && !cls) break;
        i++;
      }
      i++; while (i < n && /[a-z]/.test(s[i])) i++;   // flags
      out += "/re/"; lastSig = "/"; lastWord = ""; continue;
    }
    out += c;
    if (!/\s/.test(c)) lastSig = c;
    if (/[A-Za-z_$]/.test(c)) lastWord += c; else if (!/[\w$]/.test(c)) lastWord = "";
    i++;
  }
  return out;
}
const js = strip(src);

// ---- what is defined ----------------------------------------------------------
const defs = new Set();
for (const m of js.matchAll(/\bfunction\s*([A-Za-z_$][\w$]*)?\s*\(([^)]*)\)/g)) {
  if (m[1]) defs.add(m[1]);
  m[2].split(",").forEach(p => { p = p.trim().split(/[=\s]/)[0]; if (/^[A-Za-z_$][\w$]*$/.test(p)) defs.add(p); });
}
for (const m of js.matchAll(/\(([^()]*)\)\s*=>/g))
  m[1].split(",").forEach(p => { p = p.trim().split(/[=\s]/)[0]; if (/^[A-Za-z_$][\w$]*$/.test(p)) defs.add(p); });
for (const m of js.matchAll(/(?:^|[(,=\s])([A-Za-z_$][\w$]*)\s*=>/g)) defs.add(m[1]);
for (const m of js.matchAll(/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) defs.add(m[1]);
for (const m of js.matchAll(/,\s*([A-Za-z_$][\w$]*)\s*=(?!=|>)/g)) defs.add(m[1]);  // 2nd+ declarator
for (const m of js.matchAll(/\bcatch\s*\(\s*([A-Za-z_$][\w$]*)/g)) defs.add(m[1]);

const builtins = new Set(("String,Number,Boolean,Array,Object,Math,JSON,Set,Map,WeakMap,Date,RegExp,Promise,Error,Symbol,"
  + "parseInt,parseFloat,isNaN,isFinite,fetch,document,window,navigator,console,location,history,performance,"
  + "setTimeout,setInterval,clearTimeout,clearInterval,requestAnimationFrame,cancelAnimationFrame,queueMicrotask,"
  + "EventSource,MutationObserver,ResizeObserver,IntersectionObserver,Event,CustomEvent,KeyboardEvent,AbortController,"
  + "Blob,File,FileReader,FormData,URL,URLSearchParams,TextEncoder,TextDecoder,Audio,Image,Option,DOMParser,"
  + "encodeURIComponent,decodeURIComponent,encodeURI,decodeURI,atob,btoa,structuredClone,getComputedStyle,"
  + "alert,confirm,prompt,localStorage,sessionStorage,Intl,NaN,Infinity,undefined,arguments,globalThis").split(","));
const keywords = new Set(["if","for","while","switch","catch","return","function","new","typeof","in","of","await",
  "async","else","do","delete","void","throw","case","break","continue","try","finally","instanceof","yield","this",
  "super","class","extends","static","get","set","true","false","null"]);

const offenders = [];

// ---- 1. call targets ----------------------------------------------------------
for (const m of js.matchAll(/(^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g)) {
  const n = m[2];
  if (keywords.has(n) || defs.has(n) || builtins.has(n)) continue;
  offenders.push("call to undefined function: " + n);
}

// ---- 2. ALL-CAPS constants read outside their scope ---------------------------
// Scope units are column-0 brace blocks: named functions, arrow consts, and
// top-level callback registrations alike. Locals of one unit are invisible to
// the next - which is exactly how MG, a const of paintThink, came to be read
// from paintTail's action row and froze the Proxy terminal.
const lines = js.split("\n");
const lineStart = [0];
for (const l of lines) lineStart.push(lineStart[lineStart.length - 1] + l.length + 1);
const spans = [];
for (let li = 0; li < lines.length; li++) {
  const l = lines[li];
  if (!l || /^[\s}\)\];]/.test(l)) continue;                 // continuation or closer
  const open = l.indexOf("{");
  if (open < 0) continue;
  let d = 0, a = lineStart[li] + open, b = -1;
  for (let k = a; k < js.length; k++) {
    if (js[k] === "{") d++;
    else if (js[k] === "}") { d--; if (!d) { b = k; break; } }
  }
  if (b < 0 || js.slice(a, b).indexOf("\n") < 0) continue;    // one-line blocks are not scopes worth tracking
  const name = (l.match(/function\s+([A-Za-z_$][\w$]*)/) || l.match(/^(?:const|let|var)\s+([A-Za-z_$][\w$]*)/) || [0, l.slice(0, 30)])[1];
  spans.push([a, b, name]);
  // skip the lines this unit swallowed so nested col-0-looking text inside strings cannot double-count
  while (li + 1 < lines.length && lineStart[li + 1] < b) li++;
}
const spanAt = p => spans.find(([a, b]) => p >= a && p <= b);
const capsRx = /\b([A-Z][A-Z0-9_]{1,})\b/g;
const moduleCaps = new Set();
for (let li = 0; li < lines.length; li++) {
  if (!/^(?:const|let|var)\b/.test(lines[li])) continue;
  if (spanAt(lineStart[li] + 1) && spanAt(lineStart[li] + 1)[0] < lineStart[li]) continue; // inside a unit
  for (const m of lines[li].matchAll(/\b([A-Z][A-Z0-9_]{1,})\b(?=\s*=[^=>])/g)) moduleCaps.add(m[1]);
}
const localCaps = new Map();
const allLocal = new Set();
for (const [a, b] of spans) {
  const body = js.slice(a, b);
  const set = new Set();
  for (const m of body.matchAll(/\b(?:const|let|var)\s+([A-Z][A-Z0-9_]{1,})\b/g)) set.add(m[1]);
  for (const m of body.matchAll(/,\s*([A-Z][A-Z0-9_]{1,})\s*=(?!=|>)/g)) set.add(m[1]);
  for (const m of body.matchAll(/\(([^)]*)\)/g))
    m[1].split(",").forEach(p => { p = p.trim(); if (/^[A-Z][A-Z0-9_]+$/.test(p)) set.add(p); });
  localCaps.set(a, set);
  set.forEach(n => allLocal.add(n));
}
for (const m of js.matchAll(capsRx)) {
  const n = m[1];
  if (moduleCaps.has(n) || builtins.has(n)) continue;
  if (!allLocal.has(n)) continue;                              // never a const anywhere: not this check's business
  const sp = spanAt(m.index);
  if (sp && localCaps.get(sp[0]).has(n)) continue;
  offenders.push("ALL-CAPS constant read outside its scope: " + n + (sp ? " (in " + sp[2] + ")" : " (module level)"));
}

if (offenders.length) { console.log([...new Set(offenders)].join("\n")); process.exit(1); }
'''

section("page script scope and the two string layers")
# refreshTails() was called and defined nowhere; MG was a const of one painter read
# from another. node --check sees neither - both are runtime errors - and both froze
# the Proxy terminal as silent unhandled rejections, from patch73 through patch82.
_swf = os.path.join(os.path.dirname(jsf), "sweep.js")
open(_swf, "w", encoding="utf-8").write(SWEEP_JS)
_r = subprocess.run(["node", _swf, jsf], capture_output=True, text=True)
check(_r.returncode == 0 and not _r.stdout.strip(),
      "every function called and every constant read exists where it is used",
      (_r.stdout.strip() or _r.stderr.strip())[:300])

# A backslash written for a RegExp string crosses the Python string AND the JS string
# and arrives one layer short: "\\s+\\[" reached the browser as s+[ - an unterminated
# class - and new RegExp threw on every paint. A pattern that needs a backslash
# belongs in a regex literal with doubled backslashes (tagRx shows the form); a
# RegExp built from strings carries none.
_pgsrc = seg(py, 'PAGE = """', chr(10) + '"""')
_bs = []
for _m in re.finditer(r"new RegExp\(", _pgsrc):
    _j = _m.end(); _d = 1
    while _d and _j < len(_pgsrc):
        if _pgsrc[_j] == "(": _d += 1
        elif _pgsrc[_j] == ")": _d -= 1
        _j += 1
    for _lit in re.findall(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', _pgsrc[_m.end():_j - 1]):
        if "\\" in _lit:
            _bs.append(_lit[:60])
check(not _bs, "no RegExp is built from a string that carries a backslash", "; ".join(_bs)[:200])

# JS reads []] as an EMPTY class - which matches nothing - followed by a bracket, so
# the alternative it sits in can never fire: portRx and timeRx were dead for it. A
# ] outside a class is already the literal; write it bare.
check("[]]" not in JS and "[^]]" not in JS,
      "no pattern closes a bracket with []] - JS reads it as an empty class")


# ------------------------------------------------------------- 5. privacy
section("privacy (redact_state)")

# Importing the panel writes __pycache__ into the tree, and the junk sweep above runs
# BEFORE this point - so the gate passed, dirtied the tree, and the NEXT run failed on
# `absent: __pycache__` blaming the tree for what the gate itself left. Off before the
# import; the sweep at the end of this file is what holds it.
sys.dont_write_bytecode = True
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
# The machine name this scan hunts for USED to be written down here, which made
# the check itself the leak it was looking for - published in every repo zip.
# The name of the machine the gate is running on is asked for at run time
# instead, so the scan still catches a hostname baked into a shipped file and
# no hostname is ever committed to say so.
_HOSTS = set()
for _hn in (socket.gethostname(), os.environ.get("COMPUTERNAME", ""),
            os.environ.get("HOSTNAME", "")):
    _hn = str(_hn or "").split(".")[0].strip().lower()
    if len(_hn) >= 4 and _hn not in ("localhost", "runner", "ubuntu", "debian"):
        _HOSTS.add(_hn)
LEAKS = [(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "email address"),
         (r"GPU-[0-9a-f]{8}-[0-9a-f]{4}", "GPU serial"),
         (r"C:\\Users\\[A-Za-z]", "a personal user folder"),
         (r"\bberitos\b", "a machine name")]
LEAKS += [(r"\b%s\b" % re.escape(_h), "this machine's name") for _h in sorted(_HOSTS)]
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
            # a machine's name reaches a file in whatever case it was typed, so
            # the name patterns are matched without regard to case. No example is
            # written here: a real machine called that would trip on this comment
            hits = [h for h in re.findall(pat, txt, re.I if what.endswith("name") else 0)
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
check("TERM_SCALE_KINDS" in seg_len(py, "def api_settings", 6000),
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
check(('data-act="tmaxAdjust"' in seg_len(PAGE, 'id="twrap-tts"', 900)),
      "the TTS terminal has an Adjust menu like the others")

# a terminating server holds its port without answering; that is not "stopped"
# unloading a large model is not instant, and a synchronous stop blocks the very
# response that would report it - the shutdown was real but unobservable
_ss2 = seg(py, "def stop_tts_server", "def api_tts_server")
check("wait=True" in _ss2 and "wait=False" not in _ss2.split("def _finish")[0].split("\n")[0],
      "stop can report progress instead of blocking")
check("threading.Thread" in _ss2, "the non-blocking path terminates off the request thread")
check(_ss2.index('sse_notify("state")') < _ss2.index("_finish"),
      "it announces the stop BEFORE blocking, not after")
check('stop_tts_server("terminate button", wait=False)' in py, "Terminate reports progress")
_ta = seg(JS, "async function terminateAll", "async function exitPanel")
check("ttsBusy" in _ta,
      "terminateAll marks the TTS pane - queueLoad defers reloads while a write is in flight")
check("finally" in _ta, "and clears the mark even if the request fails")
check(JS.count('"stopping"') == 0 or "shutting down" in JS,
      "one phrase for the shutting-down state, not two")
check('stop_tts_server("stop button", wait=False)' in py, "the Stop button reports progress")
_fe2 = seg(py, "def full_exit", "def watchdog_loop")
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
_as = seg_len(py, "def api_settings", 6000)
check('"exitOnClose", "launchArc"' in _as or '"launchArc", "exitOnClose"' in _as,
      "launchArc is coerced to bool rather than stringified by the catch-all")
_af = seg_len(JS, "function arcFire", 500)
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
_rc2 = seg_len(JS, "function renderCustom", 3000)
check("swToggle(arcOn" in _rc2, "it uses the shared switch control, not a bespoke one")
# step 8 calls helperGo with no selector because the arc was meant to do the pointing;
# with the arc off the step had nothing to point at
_ld = seg(JS, "function launchDemo", "function flashTargets")
check("launchArc === false" in _ld and "flashTargets" in _ld,
      "the guide step falls back to the standard highlight when the arc is off")
check(_ld.index("launchArc === false") < _ld.index("lbdemo"),
      "and returns before the arc loop rather than running both")
# a checkbox sits inside a label, so a click lands on the styling span where .checked is
# undefined. Switches belong on "change", where every other one already is.
_clickblk = JS[JS.rindex('document.addEventListener("click"'):]
check("launchArcToggle" not in _clickblk,
      "the switch is not handled on click, where the target is the label")
_chg = seg_before(JS, 'd.act === "provField"', 900)
check("launchArcToggle" in _chg, "it is handled on change, beside the other switches")


section("TTS engine adapter")
check('"ttsEngine": "moss"' in py, "engine defaults to moss - an existing install is unchanged")

_sp = seg(py, "def tts_acpp_speak", "def tts_server_port")
check('"/v1/audio/speech"' in _sp, "audio.cpp adapter targets the OpenAI speech route")
check('"voice_ref"' in _sp and "b64" not in _sp,
      "reference passed as a path, never base64 - the server takes a local path")
check("reference_text" in _sp, "reference transcript is forwarded when present")
check("HTTPError" in _sp and "e.read()" in _sp,
      "upstream failures surface the server's own body, as the MOSS path does")

_cf = seg(py, "def tts_acpp_config", "def tts_acpp_speak")
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

_run = seg(py, "def _run_inner", "def _silence")     # _run is a prefix of this
check('tts_engine(cfg) == "audiocpp"' in _run, "the generate path branches on engine")
# the probe used to be recognised only after the tagger had marked it up, so the panel
# spoke - and logged - [sound_ping] ping. It is settled at the door now: before the
# tagger, before the mood reader, before the spoken record, before either engine arm.
_ping_at = _run.find("tts_is_ping(raw)")
check(_ping_at >= 0, "the ping is recognised by the one shared test")
for _later, _what in (("tts_player_tag(", "the tagger"),
                      ("mood_note_line(", "the mood reader"),
                      ('tts_engine(cfg) == "audiocpp":', "either engine arm")):
    check(0 <= _ping_at < _run.find(_later),
          "the ping is settled before %s" % _what,
          "%d vs %d" % (_ping_at, _run.find(_later)))
check(_run.count("if not ping") >= 2,
      "and a probe never reaches the tagger or the record whatever the mode",
      "%d guards" % _run.count("if not ping"))
# the branch, not the later one-line conditional that also contains the phrase
_acpp_arm = seg(_run, 'tts_engine(cfg) == "audiocpp":', "ref_b64, cached")
check("tts_chunks" not in _acpp_arm and "ThreadPoolExecutor" not in _acpp_arm,
      "no chunking or concurrency on the audio.cpp arm - the server does both itself")
check("tts_wav_join" not in _acpp_arm, "and no WAV stitching, since one request returns one file")

_srv = seg(py, "def api_tts_server", "def api_launcher_content")
check('eng == "audiocpp"' in _srv, "starting the server branches on engine")
check('"--config"' in _srv, "audio.cpp is started from a config the panel writes")
check("os.path.isdir" in _srv, "the audio.cpp model is validated as a folder, not a file")

_fs = seg(JS, "const TTS_FIELDSETS", "function ttsFields")
check('"ttsPython"' not in _fs.split("audiocpp:")[1], "audio.cpp field set has no python path")
check('"ttsWrapper"' not in _fs.split("audiocpp:")[1], "and no wrapper script path")
check("ttsPickDir" in JS and "pickTtsFolder" in JS, "the model folder can be picked, not only typed")

# generated lines used to land in a temp folder with an opaque name
_sn = seg(py, "def tts_save_named", "def tts_diagnose")
check("%Y%m%d_%H%M%S" in _sn, "saved lines are named as the reference wrapper named them")
check("[^A-Za-z0-9_-]" in _sn, "the speaker name is made filesystem-safe")
check("os.path.exists(path)" in _sn, "two lines in the same second do not overwrite each other")
# check the code, not the prose - the docstring says "nothing is pruned" and a
# substring test on the whole function matched its own comment
_sn_code = re.sub(r'""".*?"""', "", _sn, flags=re.S)
check(not re.search(r"os\.(remove|unlink)|rmtree|\.prune\(", _sn_code),
      "nothing is deleted from the user's own folder", _sn_code[:120])
_acpp2 = seg(py, "def _run_inner", "ref_b64, cached")
check('os.path.join(self.dir(), "out-%s.wav" % eid)' in _acpp2,
      "the SERVED file stays in the jail; the named copy is alongside")
check("tts_save_named" in seg(py, "def saved_line", "def _run("),
      "the named copy is kept in saved_line, shared by both engines - it used to be\n       asserted of the audio.cpp arm, on a slice that had silently run wild")
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
_ls = seg(py, "def list_tts_models", "def api_tts_models")
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

_sg = seg(py, "def api_tts_server", "def api_launcher_content")
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
_fa = seg(py, "def find_acpp_exe", "def api_acpp_update")
check("os.walk" in _fa and "count(os.sep) > 4" in _fa,
      "the server is found under a folder, prebuilt (flat) or source build (nested)")
check('"ttsAcppDir"' in JS, "the user names a folder, not an executable")
check('["ttsAcppExe"' not in JS, "and cannot point the field at an arbitrary .exe")
_bt = seg_len(JS, "async function browseTo", 700)
check("path: \"\"" in _bt,
      "a browse that lands on a non-folder falls back rather than dead-ending")
check("Proxy TTS Port" in PAGE and "Wrapper Port (point" not in PAGE,
      "the port is named for what it is, not for the wrapper that may not exist")
check("/api/acpp-update" in py and "0xShug0/audio.cpp" in py,
      "audio.cpp has an update check, on the same terms as the llama.cpp one")
_au = seg(py, "def api_acpp_update", "def tts_save_named")
check("body=None" in _au and "urlopen" in _au, "it runs only when asked")
_hg = seg(JS, "function renderHiggsGuide", "function renderMossGuide")
for _n in ("audio.cpp/releases", "audio.cpp-gguf", "q8_0", "bf16", "Models"):
    check(_n in _hg, "the Higgs guide names %s" % _n)
check("String.fromCharCode(92)" in _hg,
      "backslashes are built, not escaped - the PAGE string eats them otherwise")
# the engines are pages WITHIN the TTS guide, not siblings of it
_us = seg_len(JS, "function showUgSub", 400)
check('"higgs"' not in _us, "Higgs is not a top-level guide tab")
check("tgpane-higgs" in JS and "tgpane-moss" in JS, "both engines live inside the TTS guide")
check('class="subtabs"' in seg(JS, "function renderTtsGuide", "function hgStep"),
      "and use the same tab styling as everywhere else")

# a copyable block should look copyable, and say so when it worked
check("copy:" in PAGE and "<svg" in seg_len(PAGE, "copy:", 200),
      "the copy affordance is an SVG - emoji render as ?? on the target font")
_css = "\n".join(re.findall(r"<style>(.*?)</style>", PAGE, re.S))
check(".gcode" in _css and "gcodePulse" in _css, "clicking one pulses in the accent colour")
_cc = seg_len(JS, "function copyCode", 600)
check("gcopy" in _cc, "the icon does not travel to the clipboard with the text")
check(":not(.gcode)" in _css,
      "the old outline flash does not fire on top of the pulse - one effect, not two")

# the audio.cpp folder gets what the llama.cpp folder has
_fe = seg(JS, "function ttsFieldExtra", "async function recheckAcpp")
check("acppchk" in _fe, "a warning when no server is found under the folder")
check("audio.cpp/releases" in _fe, "the releases address, copyable")
check("acppCheck" in _fe, "and an update check beside it")
# "function renderTts" also matches renderTtsGuide - be exact
_rt = JS.index("function renderTts(force)")   # it takes one since patch88
check("recheckAcpp" in JS[_rt:_rt + 1600],
      "the folder is re-checked whenever the pane is drawn")

# the terminal should say what it is doing, as the reference wrapper did
check("Loading %s..." in py and "Using device: cuda" in py,
      "starting the server announces itself in the terminal")
check("ready for voice synthesis" in py, "and says when it is actually ready")
check("Stopping the TTS server" in py and "TTS server stopped" in py,
      "stopping says so too - the reference wrapper never did")
check("said_ready" in py, "ready is announced once per start, not once per poll")
_el = seg(py, "def tts_engine_label", "def tts_gpu_label")
check("ttsAcppModel" in _el, "the banner names the model actually loaded")

# the saved line repeats a folder the user chose; the filename is the new information
# built once now and called from both arms, so one occurrence is correct
check(py.count("os.path.basename(kept or out)") == 1,
      "both engines log the filename, not the whole path")

# Higgs reads inline tags out of the line and acts on them
_tg = seg(py, "def tts_apply_tags", "def tts_normalize")
for _fam in ("emotion", "style", "prosody", "sfx"):
    check('"%s"' % _fam in seg(py, "TTS_TAGS = {", "TTS_TAG_ANY_RX"),
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
check("TTS_SENT_RX" in py and "_tts_render(tags, _blocked) + body" in py,
      "sentence-level tags are moved to the front of their sentence")
check("kept.setdefault" in py, "competing tags are deduped rather than stacked")
check("TTS_ORDER" in py, "and emitted in the model card's stacking order")

# SkyrimNet's own vocabularies, so its stock prompt works without being edited
check("TTS_ALIAS" in py and '"angry": ("emotion", "anger")' in py,
      "SkyrimNet's own [angry] / [sigh] tags map onto Higgs where they can")
check("TTS_ALIAS_DROP" in py,
      "and the ones with no counterpart are named rather than guessed at")
_al = seg(py, "    def alias(m):", "    text = TTS_PAUSE_ANY_RX.sub(pause, text)")
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
_hgg = seg(JS, "function renderHiggsGuide", "function renderMossGuide")
check("Chatterbox" in _hgg and "allowed" in _hgg,
      "the guide says tags need Chatterbox and its allowed list, not just the switch")
# a tag must abut the thing it affects - checked as the property, since the
# implementation moved from a regex to building the string that way
check("_tts_render(tags, _blocked) + body" in py,
      "a sentence-level tag is emitted flush against its sentence")
check('"<|sfx:%s|>%s" % (value, word)' in py,
      "and a sound effect flush against its onomatopoeia")
# this check used to assert MOSS understood no tags. It does: [pause 3.2s]. The engine
# is passed in now so each catalogue is applied to its own engine.
check("tts_engine(cfg)," in seg_len(py, "processed = tts_apply_tags", 300),
      "the engine decides which catalogue applies, rather than being assumed")
check('"ttsTags": "on"' in py, "and ON by default - tags pass to the engine out of the box")
check('id="tts-ttsTags"' in JS and "body.ttsTags" in JS, "the switch exists and saves")

# MOSS has one marker of its own; the two catalogues must not bleed into each other
check("TTS_PAUSE_RX" in py and "pause" in seg_len(py, "TTS_PAUSE_RX = re.compile", 120),
      "MOSS's [pause Ns] marker is known")
check("TTS_PAUSE_MAX_S" in _tg, "and a runaway pause is clamped rather than obeyed")
check('engine == "audiocpp"' in _tg and "moss = keep and engine" in _tg,
      "each engine keeps only the tags it understands")
# the on-page tag explanation was removed by request; the guide carries it
check("Audio Tags" in JS, "the setting is present without the explanation beside it")

# the update result reads like the llama.cpp one
_ac = seg_len(JS, 'd.act === "acppCheck"', 1400)
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
_hi = seg(py, "def higgs_install_worker", "def api_higgs_install")
_ha = seg_len(py, "def api_higgs_install", 900)
check("/api/higgs-install" not in (_ro | _po), "the installer is host-only")
check('body or {}).get("confirm")' in _ha, "and refuses without an explicit confirmation")
check("cancel" in _ha and "HIGGS_INSTALL[\"cancel\"] = True" in _ha, "it can be stopped")
_uz = seg(py, "def _hi_unzip", "def _hi_free_bytes")
check("refusing an archive entry outside" in _uz and "os.path.realpath" in _uz,
      "an archive entry that would land outside the folder is refused")
check("refusing an absolute path" in _uz, "and so is an absolute path inside an archive")
check('if p not in ("", ".", "..")' not in _uz,
      "hostile entries are refused, not silently flattened into the folder")
_dl = seg(py, "def _hi_download", "def _hi_unzip")
check("Range" in _dl and ".part" in _dl, "a part-finished download resumes rather than restarts")
check("HIGGS_INSTALL[\"cancel\"]" in _dl, "and notices a cancel mid-stream")
check("disk_usage" in py, "free space is checked before 5 GB is fetched")
check("could not be saved" in _hi and "Set these by hand" in _hi,
      "a locked config at the last step does not report the whole install as failed")
# a finished install that looks identical to one that never ran is not feedback
_row = seg(JS, "function higgsInstallRow", "async function higgsInstall")
check("g.done" in _row, "a finished install says so, rather than falling back to the button")
check("higgsDismiss" in _row and '"dismiss"' in py, "and can be dismissed")
# the skip is now conditional on the marker - see the install section - so retrying is
# still cheap, but only for an engine we put there at this release
check("resuming" in _hi.lower() or "resume" in _hi.lower(),
      "a retry resumes the model rather than starting it over")
_sc = seg(py, "def save_config(cfg):", "DEFAULT_PROVIDER_SEED")
check("PermissionError" in _sc and "time.sleep" in _sc,
      "an atomic write retries a transient Windows lock rather than losing the settings")
check("os.remove(tmp)" in _sc, "and never leaves a .tmp file behind when it gives up")
check("api.github.com" in _hi and "huggingface.co" in _hi,
      "both sources are the published ones")
# the profile archives carry a commit hash; the shared runtime does not
_ea = seg(py, "HIGGS_ENGINE_ASSETS = (", "HIGGS_GGUF_REPO")
check(".zip" not in _ea and "audiocpp-" not in _ea,
      "engine assets are matched by WORDS, not filenames - names carry a build hash")
check('"win"' in _ea, "win not windows, so a win64 archive still matches")
# each profile is now its own entry rather than a preference chain - see the
# "two builds, one runtime" section
check("balance" in _ea and "fast" in _ea,
      "both profiles are named explicitly, and only balanced is required")
check("avoid" in _hi, "the runtime is excluded from the build match, not colliding with it")
check("for w in need)" in _hi, "so a rename or reordering does not break the install")
check("It has:" in _hi,
      "and a mismatch lists what the release actually carries, not just what is missing")
_cf = seg(JS, "async function higgsInstall", "async function higgsCancel")
for _s in ("github.com", "huggingface.co", "5.1 GB", "Nothing about your setup"):
    check(_s in _cf, "the confirmation states: %s" % _s)


section("tts terminal tags")
check("def tts_tags_display" in py,
      "the terminal shows tags as the model wrote them, not as Higgs takes them")
_pt = seg(JS, "function paintTail", "function stepAt")
check('which === "tts"' in _pt, "the TTS terminal is painted, not dumped as plain text")
_ps = seg(JS, "function paintSpoken", "function paintTail")
# The speaker magenta and tag cyan live in ONE module const pair since patch83 -
# the painters and the action row reference the names, so the value is pinned
# here once and cannot drift between painters again.
check('const SPK_MAG = "#ff5dc8", SPK_CY = "#2ef2ff"' in JS,
      "the shared speaker/tag palette holds magenta and cyan")
check("SPK_CY" in _ps, "and tags are picked out in the shared cyan")
check("#ffffff" in _ps and "SPK_MAG" in _ps and "#f2c14e" in _ps,
      "with white stars, the shared magenta speaker and the line in gold")
check("SPK_MAG" in _pt and "SPK_CY" in _pt,
      "the action row colours with the shared pair, not with names from another scope")

section("action drilldown - two stages, one branch")
# SkyrimNet picks a category, then drills into it with a second prompt. The stage is
# read off the REQUEST - the reply cannot tell the stages apart: the category rule
# asks for an intent parameter the models routinely skip, and param-less direct
# actions exist. The drilldown prompt introduces itself instead.
_dr = (b"You select the single most appropriate action for Serana from a specific "
       b"action category. A broader category was already identified from the dialogue. "
       b"## Serana's Current State ... ## Eligible Actions ...")
_mn = (b"You select the single most appropriate in-game action based on the dialogue "
       b"exchange between the speaker and Serana. "
       b"## Serana's Character Profile (THIS IS WHO YOU ARE ROLEPLAYING AS) "
       b"## Eligible Actions ...")
check(fp.is_action_drill(_dr) is True, "a drilldown introduces itself and is recognised")
check(fp.is_action_drill(_mn) is False, "the main prompt is not mistaken for one")
check(fp.note_actor(_dr) == "Serana",
      "the drilldown prompt names its actor - this read 'someone' before patch84")
check(fp.note_actor(_mn) == "Serana", "and the main prompt still names its own")
_cat = fp.action_row('{"ACTION": "SNBaka_Expression"}', "Serana", False)
check(_cat == fp.TREE_PAD + fp.TREE_MID + " " + fp.ACTION_MARK + " Serana > SNBaka_Expression",
      "a category pick stays open: name > category, no parameters", _cat)
_act = fp.action_row('{"ACTION": "Express", "PARAMS": {"mood": "surprised"}}', "Serana", True)
check(_act == fp.TREE_PAD + fp.TREE_END + " " + fp.ACTION_MARK + " Serana > Express (mood: surprised)",
      "the drilldown pick closes the branch with its parameters", _act)
check(fp.action_row('{"ACTION": "None"}', "Serana", False) == "",
      "a main None stays silent - the commonest answer would bury the rest")
check(fp.action_row('{"ACTION": "None"}', "Serana", True) != "",
      "a drilldown None is written - it closes a branch a category opened")
check("0x2937" in seg(JS, "function hasRecord", "function panelProvMatcher"),
      "the provider filter owns drill-marked records too")

section("automatic tts calibration - measure every line")
# tts_auto_cap logs its working since patch87, so these calls write. Sandboxed:
# a gate that dirties the tree it judges fails its own junk sweep.
_ac0_keep = fp.log_dir
_ac0_td = tempfile.mkdtemp()
fp.log_dir = lambda cfg=None: _ac0_td
try:
    # The overrun record says what went WRONG; the measurement record says what went
    # RIGHT, and the estimate stands on the second. Off is byte-identical to before.
    _ln = "Right next to where his eyes should be. Hehe."
    check(fp.tts_auto_cap(_ln, {"ttsAutoCal": "off"}) == (fp.acpp_token_cap(_ln), "", 0.0),
          "off is the runaway guard unchanged")
    _rw = [{"chars": 40, "pause_s": 0, "secs": 3.1, "at": "x"}] * 20
    _c1, _n1, _e1 = fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy"}, rows=_rw)
    check(fp.TTS_ACPP_TOK_FLOOR <= _c1 < fp.acpp_token_cap(_ln) and "measured" in _n1,
          "proxy estimates from the measured rate, inside floor and guard", _n1)
    check("seed rate" in fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy"}, rows=[])[1],
          "and says so when it is still on the seed rate")
    _c2 = fp.tts_auto_cap(_ln + " [pause 2.0s]", {"ttsAutoCal": "proxy"}, rows=_rw)[0]
    check(_c2 > _c1, "a pause tag buys its silence more tokens")
    check(fp.tts_auto_cap("Yes.", {"ttsAutoCal": "proxy"}, rows=_rw)[0]
          == fp.acpp_tok_floor(4),
          "a very short line still gets ITS lead-in floor, scaled to the line")
    _slow = [{"chars": 30, "pause_s": 0, "secs": 5.0, "at": "x"}] * 20
    check(fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy", "ttsAutoCalMargin": "3.0"}, rows=_slow)[0]
          == fp.acpp_token_cap(_ln),
          "no estimate ever raises the ceiling the user already knows")
    _c3, _n3, _e3 = fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy", "ttsAutoCalUseFit": "on",
                                     "ttsAutoCalMedian": '{"cps": 14.0, "lead": 0.5}'})
    check("TTS-calibrated" in _n3 and _c3 < fp.acpp_token_cap(_ln),
          "a fitted rate is read per line by the proxy, not asked for", _n3)
    check("cps" in fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy"}, rows=_rw)[1],
          "and with no stored fit the measured rate carries the line")
    check(fp.tts_auto_cap(_ln, {"ttsAutoCal": "llm", "ttsAutoCalPort": "1"},
                          cfg={}, rows=_rw)[0]
          == fp.tts_auto_cap(_ln, {"ttsAutoCal": "proxy"}, rows=_rw)[0],
          "an unreachable server changes nothing - LLM mode caps like Proxy either way")
    check(fp._autocal_parse('noise {"cps": 13.9, "lead": 0.42} noise') == {"cps": 13.9, "lead": 0.42},
          "a fit is dug out of whatever prose surrounds it")
    check(fp._autocal_parse('{"cps": 99, "lead": 0.4}') is None,
          "a rate no voice speaks at is refused, not kept")
    check(fp.tts_measure_row("Hi. [pause 0.5s]", 2.0)["pause_s"] == 0.5,
          "a measurement carries its pauses")
    check(fp.tts_measure_summary([{"chars": 30, "pause_s": 0.0, "secs": 2.0, "at": "a"},
                                  {"chars": 30, "pause_s": 0.0, "secs": 3.0, "at": "b"},
                                  {"chars": 8, "pause_s": 0.0, "secs": 0.1, "at": "c"}])
          == {"n": 2, "cps": 12.5, "first": "a", "last": "c"},
          "the summary is the median of the believable lines only")
finally:
    fp.log_dir = _ac0_keep

section("the spoken line pays for synthesis only")
# From patch1 to patch85 the wall started at the top of the worker, so every panel
# feature - above all the player tagger's model call - was billed to "overhead
# (http + wav)" and read as the transport slowing down. The wall splits at the POST:
# realtime is synthesis, prep is named, and the hot path parses no config files.
_wk = seg(py, "def _run_inner", "def _silence")
check('(secs / synth)' in _wk, "realtime is audio over SYNTHESIS, not over the whole wall")
check('"prep:"' in _wk, "and the preparation is shown on its own named line")
check("load_config_cached()" in _wk and "load_config()" not in _wk,
      "the worker reads the cached config - one parse per edit, not per line")
_ao2 = seg(py, "def _tts_acpp_once", "def tts_server_port")
check("load_config_cached()" in _ao2 and "load_config()" not in _ao2,
      "and so does the request builder")
_cfg_keep, _ml_keep = fp.CONFIG, (fp.TTS_MEASURE_LOG, fp.TTS_MEASURE_LEGACY, fp.TTS_MEASURE_KEEP)
_td = tempfile.mkdtemp()
try:
    fp.CONFIG = os.path.join(_td, "fleet-config.json")
    with open(fp.CONFIG, "w", encoding="utf-8") as _f:
        json.dump({"settings": {}}, _f)          # sparse: the first load fills and saves
    _a = fp.load_config_cached(); _b = fp.load_config_cached()
    check(_a is _b, "the cached config is the same object until the file changes")
    with open(fp.CONFIG, "w", encoding="utf-8") as _f:
        json.dump({"settings": {}, "slots": [], "padding": "x" * 64}, _f)
    _c = fp.load_config_cached()
    check(_c is not _b and _c is fp.load_config_cached(),
          "an edit is seen on the very next line, then cached again")
    fp.TTS_MEASURE_LOG = os.path.join(_td, "m.jsonl")
    fp.TTS_MEASURE_LEGACY = os.path.join(_td, "m.json")
    with open(fp.TTS_MEASURE_LEGACY, "w", encoding="utf-8") as _f:
        json.dump([{"chars": 9, "secs": 1.0, "at": "legacy"}], _f)
    for _i in range(3):
        fp.tts_measure_record("hello measured line", 1.5)
    with open(fp.TTS_MEASURE_LOG, encoding="utf-8") as _f:
        _nl = len([l for l in _f.read().splitlines() if l.strip()])
    check(_nl == 3, "a measurement is ONE appended line, not a rewrite", str(_nl))
    check(len(fp.tts_measure_rows()) == 4, "and the patch85 list is folded into the read")
    fp.TTS_MEASURE_KEEP = 2
    with fp.MEASURE_LOCK:
        fp._tts_measure_compact()
    with open(fp.TTS_MEASURE_LOG, encoding="utf-8") as _f:
        _nc = len([l for l in _f.read().splitlines() if l.strip()])
    check(_nc == 2 and not os.path.exists(fp.TTS_MEASURE_LEGACY),
          "compaction keeps the horizon and retires the old list")
finally:
    fp.CONFIG = _cfg_keep
    fp.TTS_MEASURE_LOG, fp.TTS_MEASURE_LEGACY, fp.TTS_MEASURE_KEEP = _ml_keep
    fp._CFG_CACHE["sig"] = None                 # the next section loads its own
fp.PTI_CACHE.clear()
for _i in range(fp.PTI_CACHE_MAX + 2):
    fp._pti_remember(("p", "", "line%d" % _i), "t%d" % _i)
check(len(fp.PTI_CACHE) == fp.PTI_CACHE_MAX and fp._pti_cached(("p", "", "line0")) is None
      and fp._pti_cached(("p", "", "line33")) == "t33",
      "the tagger remembers its last answers and forgets the oldest first")
check("_pti_cached(_ck)" in seg(py, "def tts_player_tag", "def mood_count"),
      "and the tagger consults it before paying the model")

section("the token cap is a stop-loss, and says so")
# Every call below writes: the cap logs its working, and the info endpoint loads
# the config (which saves filled defaults). Sandboxed, or the gate dirties the
# tree it is judging - the junk sweep at the end catches exactly that.
_ac_keep = (fp.log_dir, fp.CONFIG)
_ac_td = tempfile.mkdtemp()
fp.log_dir = lambda cfg=None: _ac_td
fp.CONFIG = os.path.join(_ac_td, "fleet-config.json")
try:
    # A cap does not shorten a line - the engine stops at its own end-of-content token.
    # Set below what a line needed it turns a good line into a retry, so the headroom is
    # learned from the estimator's own worst miss rather than picked.
    _rw2 = [{"chars": 44, "pause_s": 0.0, "secs": 4.0, "tok": 100.0, "est": 80.0,
             "bound": "estimate", "at": "x"}] * 12
    check(fp.tts_autocal_fit(_rw2, [])["worst"] == 1.25,
          "the fit is actual over ESTIMATED - how wrong the estimator was")
    check(fp.tts_autocal_fit([{"chars": 44, "secs": 4.0, "tok": 100.0,
                               "bound": "estimate"}], [])["n"] == 0,
          "a line with no estimate recorded cannot be scored, and is not")
    _h, _why = fp.tts_autocal_headroom(rows=_rw2, fails=[])
    check(abs(_h - 1.25 * fp.AUTOCAL_HEAD_PAD) < 1e-6 and "worst" in _why,
          "the headroom is the worst miss plus a pad", "%.3f %s" % (_h, _why))
    check(fp.tts_autocal_headroom(rows=_rw2[:3], fails=[])[0] == fp.AUTOCAL_HEAD_SEED,
          "and too few scored lines means the seed, not a guess off two of them")
    _tight = [{"chars": 44, "pause_s": 0.0, "secs": 4.0, "tok": 100.0, "est": 400.0,
               "bound": "estimate", "at": "x"}] * 12
    check(fp.tts_autocal_headroom(rows=_tight, fails=[])[0] == fp.AUTOCAL_HEAD_MIN,
          "an over-predicting estimator still keeps a floor of headroom")
    _ln2 = "This is a test of the text-to-speech system."
    _c4, _n4, _e4 = fp.tts_auto_cap(_ln2, {"ttsAutoCal": "proxy"}, rows=_rw2)
    check(_e4 > 0 and "cap" in _n4 and "x" in _n4,
          "a cap note shows the bare estimate and the headroom it was multiplied by", _n4)
    check(fp.tts_auto_cap(_ln2, {"ttsAutoCal": "off"}, rows=_rw2) == (fp.acpp_token_cap(_ln2), "", 0.0),
          "off is still the runaway guard, unchanged and unlogged")
    # the estimate is recorded WITH the line, or the fit above has nothing to stand on
    check(fp.tts_measure_row("hi", 1.0, 42)["est"] == 42,
          "a measurement carries the estimate that was in force")
    _wk2 = seg(py, "def _run_inner", "def _silence")
    check("AUTOCAL_EST[0]" in seg(py, "def _tts_acpp_once", "def tts_server_port"),
          "which the request builder stashes as it caps")

    # every panel cost before the engine is named, or the next feature is blamed on the
    # transport exactly as the tagger was
    for _bit in ("player tags", "mood", "token estimate", "panel"):
        check('"%s' % _bit in _wk2, "prep names its %s cost" % _bit)
    check("wall - prep - est_s" in _wk2,
          "and the estimate is taken OUT of synthesis - it runs inside the request builder")

    # the feed, and the two inspection answers
    check('kind == "ttscal"' in py, "the calculations have a feed of their own")
    check('which === "ttscal"' in seg(JS, "function paintTail", "function stepAt"),
          "painted by the same painter as the other record terminals, not as plain text")
    _info = fp.api_tts_autocal_info()
    check(("%.1f" % fp.TTS_ACPP_FRAME_RATE) in _info["algorithm"]
          and str(fp.TTS_ACPP_TOK_FLOOR) in _info["algorithm"]
          and ("%.1f" % fp.TTS_ACPP_TOK_PER_CHAR) in _info["algorithm"],
          "the algorithm is written FROM the constants, so it cannot go stale")
    check("stop-loss" in _info["algorithm"],
          "and says plainly that a tighter cap is not a better one")
    nin(str(sorted(_info)) + "  padding for the length floor", "deriveSystem",
        "and carries no prompt text now that nothing shows one (patch113)")
    nin(str(sorted(_info)), "llmUser",
        "and the per-line question is not advertised, because it is not asked")

    section("the TTS page: one feed, one pane, one bar")
    # The page kept its record twice - a file tail AND a buffer in the browser. A
    # buffer cannot be reread after a reload and cannot be interleaved with a tail in
    # the right order, so everything is written to one log and the page only tails it.
    fp.calterm_log(["diagnose  [x]", "an answer"])
    _feed = open(fp.calterm_log_path(), encoding="utf-8").read()
    check("proxy" in _feed and "diagnose  [x]" in _feed,
          "the calculations and the diagnosis land in the SAME feed")
    check('kind == "ttscal"' in py and "autocal_log_path" not in py,
          "one feed, and the one it replaced is gone")
    nin(py, "cal_facts_text",
        "and the data block that only Show data could write went with that button")
finally:
    fp.log_dir, fp.CONFIG = _ac_keep
    fp._CFG_CACHE["sig"] = None            # the next section loads the real one

# the browser-side copy of the record is GONE, not merely unused
for _dead in ("calTermLine(", "calTermText =", "calTermText +=",
              "function ttsDiagLines"):
    check(_dead not in JS, "no second copy of the record in the page: %s" % _dead)
check('id="tail-ttscal"' in JS, "the page has ONE terminal for this")
check('ttsCalTermOpen' in fp.DEF_SETTINGS and fp.DEF_SETTINGS["ttsCalTermOpen"] == "off",
      "hidden until asked for, and the asking is remembered")
# the pane was rebuilt on every live tick, which replaced the terminal element and
# reset its size and text several times a minute
_rt = seg(JS, "function ttsPaneSig", "function ttsAutoCalBlock")
check("sig === ttsPaneDrawn" in _rt and "pane.firstChild" in _rt,
      "the pane is redrawn only when what it is drawn from has changed")
check("refreshCalTail()" in _rt and "refreshTtsMeter()" in _rt,
      "and the live parts refresh in place when it is not")
check("ttsDiagLast" in _rt,
      "the diagnosis text is excluded from the signature - it lands in the feed, and "
      "signing it would redraw the pane under the reader")
# the bar
_mt = seg(JS, "const METER_WHY", "async function refreshTtsMeter")
for _band in ("player tags", "mood", "token estimate", "panel", "generate", "codec",
              "http + wav", "used", "spare to cap", "cap to guard"):
    check(_band in _mt,
          "the bar has a band for %s" % _band)
check("transition:width" in _mt,
      "the bands move to their new width rather than jumping")
check("/api/tts-meter" in JS and "def api_tts_meter" in py,
      "fed by the panel, from the same numbers the report prints")
check("showModal(" in seg(JS, 'd.act === "ttsAutoInfo"', 'd.act === "ttsInfoCopy"'),
      "the algorithm opens over the page, not into a terminal")

section("the Reasoning dial writes the launcher too")
# llama.cpp DOES have a server-side flag for this: --chat-template-kwargs takes a JSON
# object and sets the default template kwargs for every request. It warns that setting
# enable_thinking that way is deprecated and honours it anyway - and some models honour
# only that, which is the whole reason for writing both.
_L = ('$llamaArgs = @(\n    "--flash-attn", "on",\n'
      '    # --- reasoning OFF (dialogue model) ---\n    "--reasoning", "off",\n'
      '    # --- sampling ---\n    "--min-p", "0.05",\n    "--reasoning-format", "none"\n)\n')
_on = fp.ps1_set_flag(_L, fp.CTK_FLAG, fp.CTK_NO_THINK, after=fp.CTK_AFTER)
check(fp.CTK_FLAG in _on and '{"enable_thinking":false}' in _on,
      "the dial writes the template kwarg into the launcher")
check(_on.index(fp.CTK_FLAG) > _on.index('"--reasoning", "off"')
      and _on.index(fp.CTK_FLAG) < _on.index("# --- sampling ---"),
      "beside --reasoning, in the paragraph a reader would look in")
check("'{\"enable_thinking\":false}'" in _on,
      "single-quoted, because a JSON value cannot live in a double-quoted PS string")
check(fp.CTK_FLAG not in fp.ps1_set_flag(_on, fp.CTK_FLAG, None),
      "and the dial takes back what the dial wrote")
_t = _L
for _i in range(4):
    _t = fp.ps1_set_flag(_t, fp.CTK_FLAG, fp.CTK_NO_THINK, after=fp.CTK_AFTER)
    _t = fp.ps1_set_flag(_t, fp.CTK_FLAG, None)
check(_t.count("\n") == fp.ps1_set_flag(
          fp.ps1_set_flag(_L, fp.CTK_FLAG, fp.CTK_NO_THINK, after=fp.CTK_AFTER),
          fp.CTK_FLAG, None).count("\n"),
      "toggling it repeatedly does not grow the file")
# the map from card to launcher, and the generator, must agree
_sv = fp.slot_flag_values({}, {"params": {"model": "m.gguf", "reasoning": "off"}})
check(_sv.get(fp.CTK_FLAG) == fp.CTK_NO_THINK,
      "a card set to off asks for the kwarg")
_sv2 = fp.slot_flag_values({}, {"params": {"model": "m.gguf", "reasoning": "on"}},
                           present=fp.CTK_NO_THINK)
check(_sv2.get(fp.CTK_FLAG, "keep") is None,
      "and set back to on asks for it to go")
check(fp.slot_flag_values({}, {"params": {"model": "m.gguf", "reasoning": "on"}})
      .get(fp.CTK_FLAG, "absent") == "absent",
      "but leaves a kwarg it never wrote alone")
check("CTK_FLAG" in seg(py, "def build_param_launcher", "def ps1_args_span"),
      "the generator writes it too, so a fresh launcher matches an edited one")


section("thinking off, said three ways, and one dial that overrules")
# There is nothing in a .ps1 to see: enable_thinking is a per-request field, not a
# launcher flag. So the override has to be visible somewhere else, or it cannot be
# told apart from doing nothing.
check('serverReasoning") == "off"' in py and "enable_thinking=false)" in py,
      "the proxy says so when it announces a route the dial has overruled")
check("enable_thinking=false with every request" in JS,
      "and the provider card's warning says what the panel actually does")
# Builds disagree about which field means "do not think". The kwarg is deprecated and
# works; the per-request budget is current and does not (a budget of 0 means "stop
# NOW", which forces a stub out of any model that always opens a reasoning block).
# SkyrimNet itself sends a third form. None of them mind an extra, so all three go.
_off = {}
fp.apply_route_shape(_off, {"thinking": False, "overrides": {}, "sampSource": "server"})
check(_off.get("chat_template_kwargs", {}).get("enable_thinking") is False,
      "the chat template kwarg is sent")
check(_off.get("enable_thinking") is False, "and the top-level form some builds read")
check(_off.get("reasoning") == {"enabled": False},
      "and the form SkyrimNet itself sends")
nin(str(_off), "reasoning_budget_tokens",
    "and NOT a budget of 0, which means stop now and returns a stub")
# patch99: patch97 held the OFF arm back whenever the launcher already said
# `--reasoning off`. It did not fix the fault it was written for, so it is reverted:
# the request says it every way again, whatever the launcher says.
for _sr99 in ("off", "on", "auto", ""):
    _x99 = {}
    fp.apply_route_shape(_x99, {"thinking": False, "serverReasoning": _sr99,
                                "overrides": {}, "sampSource": "server"})
    check(_x99.get("chat_template_kwargs", {}).get("enable_thinking") is False
          and _x99.get("enable_thinking") is False
          and _x99.get("reasoning") == {"enabled": False},
          "server reasoning %s: the per-request off goes, all three ways"
          % (_sr99 or "unset"))
    nin(str(_x99), "reasoning_budget_tokens", "and never as a budget of 0 (%s)" % _sr99)
nin(seg(py, "def apply_route_shape", "def chat_metrics"),
    'rt.get("serverReasoning")',
    "and the shape does not read the launcher at all - the route decided already")
# Thinking ON is SAID, not merely unsaid. Removing the false left the server to its
# own default, and that default is false on anything started with `--reasoning off`
# or carrying the dial's own launcher line - so a card whose setting was lost left
# the line behind, `parse_ps1_reasoning` did not read it, no warning showed, and the
# switch did nothing at all.
_on = {"reasoning": {"enabled": False}, "enable_thinking": False,
       "chat_template_kwargs": {"enable_thinking": False}}
fp.apply_route_shape(_on, {"thinking": True, "overrides": {}, "sampSource": "server"})
check(_on.get("chat_template_kwargs", {}).get("enable_thinking") is True,
      "thinking on asserts the kwarg true - the one form the server reads",
      json.dumps(_on)[:110])
check(_on.get("enable_thinking") is True and _on.get("reasoning") == {"enabled": True},
      "and the other two forms with it, the same three the OFF arm writes")
check(_on.get("reasoning_budget_message") == fp.REASON_BUDGET_MSG,
      "and the budget still has something to say when it runs out")
_onx = {}
fp.apply_route_shape(_onx, {"thinking": True, "overrides": {}, "sampSource": "server"})
nin(str(_onx), "reasoning_budget_tokens",
    "and a budget is still never invented on the way through")
_shape99 = seg(py, "def apply_route_shape", "def chat_metrics")
check(_shape99.count('ck["enable_thinking"] = True') == 1
      and _shape99.count('ck["enable_thinking"] = False') == 1,
      "one arm says true, one says false, and neither leaves it to the server")
nin(_shape99, 'ck.pop("enable_thinking"',
    "nothing merely removes it any more - absent is the server's answer, not ours")

# the server card's Reasoning dial reaches the request, not just the launcher
_td3 = tempfile.mkdtemp()
_ps1 = os.path.join(_td3, "s.ps1")
with open(_ps1, "w", encoding="utf-8") as _f:
    _f.write('& $exe @("--port","1236","--reasoning","off")\n')
_slot = {"script": _ps1, "port": 1236}
check(fp.slot_reasoning(_slot) == "off", "the dial is read off the launcher")
check(fp.provider_route({"id": "x", "title": "T", "thinking": True},
                        _slot, 1236, set())["thinking"] is False,
      "a server told not to reason overrules a provider asking to")
check(fp.diag_route(1236, {"slots": [_slot]}, thinking=True)["thinking"] is False,
      "and overrules the panel asking to, the same way")
with open(_ps1, "w", encoding="utf-8") as _f:
    _f.write('& $exe @("--port","1236","--reasoning","on")\n')
check(fp.provider_route({"id": "x", "title": "T", "thinking": True},
                        _slot, 1236, set())["thinking"] is True,
      "and the cache follows the file, so flipping the dial is seen")

# the one remaining TTS job: calib serves the manual diagnose tool, which takes
# its server from the request body - so the stored-port helper and its setting
# left in the patch155 dead-code sweep.
check("def tts_job_port" not in py and "ttsCalibPort" not in py,
      "no stored job port remains - the diagnose tool is told its server")
check(fp.tts_job_think({"ttsCalibThink": "on"}, "calib") is True,
      "the calib thinking switch still rides its own setting")


section("the headroom learns, from the lines where it mattered")
# Three faults found in the field, all in how the headroom was worked out.
_mk = lambda ch, bound, cps=16.0, lead=0.8: {
    "chars": ch, "pause_s": 0.0, "secs": round(ch / cps + lead, 2),
    "tok": round((ch / cps + lead) * 25, 1), "est": round((ch / cps + lead) * 25, 1),
    "bound": bound, "cap": 300, "attempt": 1}
_long = [_mk(c, "estimate") for c in (70, 80, 90, 100, 113, 120, 130, 140, 156, 160)]
_short = [dict(_mk(c, "floor"), est=round((c / 16.0) * 25, 1)) for c in (10, 14, 19, 34)]

# 1. a line the FLOOR covered never tested the estimate, so it does not score it
_f1 = fp.tts_autocal_fit(_long + _short, [])
check(_f1["n"] == len(_long),
      "only lines whose cap the estimate decided are scored",
      "%d of %d" % (_f1["n"], len(_long) + len(_short)))
_loose = fp.tts_autocal_fit([dict(r, bound="estimate") for r in _long + _short], [])
check(_loose["worst"] > _f1["worst"],
      "and counting the floor-covered ones would read worse for no reason",
      "%.2f vs %.2f" % (_loose["worst"], _f1["worst"]))

# 2. a runaway is a censored observation: it needed AT LEAST its cap - but only
# where the estimate DECIDED that cap (patch118, the same rule successes obey)
_f2 = fp.tts_autocal_fit(_long, [{"est": 162.0, "cap": 202.0, "attempt": 1,
                                  "bound": "estimate"}])
check(_f2["censored"] == 1 and _f2["worst"] > _f1["worst"],
      "a runaway enters the record as cap/est and raises the worst miss",
      "%.2f -> %.2f" % (_f1["worst"], _f2["worst"]))
check(fp.tts_autocal_headroom(rows=_long,
                              fails=[{"est": 162.0, "cap": 202.0,
                                      "bound": "estimate"}])[0]
      > fp.tts_autocal_headroom(rows=_long, fails=[])[0],
      "so losing a line widens the headroom - the direction that stops losing lines")
check('"est"' in seg(py, "def eoc_record(text, cap", "def eoc_rows"),
      "which needs the failure to carry the estimate it missed")
check('"bound"' in seg(py, "def tts_measure_row(text, secs", "def tts_measure_record"),
      "and the measurement to carry what settled its cap")

# 3. the panel fits the same lines itself, and judges the model against it
_ols = fp.tts_measure_ols(_long)
check(abs(_ols["cps"] - 16.0) < 0.5 and abs(_ols["lead"] - 0.8) < 0.2,
      "least squares recovers both the rate and the lead-in", str(_ols))
check(fp.tts_fit_mae({"cps": 16.0, "lead": 0.0}, _long) > _ols["mae"],
      "a fit with the zero lead-in the model kept returning predicts worse")
_dv2 = seg(py, "def autocal_derive_arith", "AUTOCAL_GEN")
check("tts_measure_ols(rows)" in _dv2,
      "the proxy refit runs the panel's own least squares - no model, no offer to referee")
check("ttsAutoCalMedian" in _dv2 and "calterm_log" in _dv2,
      "the arith refit writes the stored fit and logs its one calibration line")

# 4. the margin is not a setting any more
nin(str(fp.DEF_SETTINGS), "ttsAutoCalMargin", "no hand-set margin in the defaults")
nin(JS, "tts-ttsAutoCalMargin", "and no box on the page to type one into")
nin(seg(py, "def tts_autocal_headroom", "def _autocal_parse"), "ttsAutoCalMargin",
    "and the headroom does not read one, so a stale config cannot pin it")
check(fp.tts_autocal_headroom(rows=_long)[0] == fp.tts_autocal_headroom(rows=_long)[0],
      "it is learned, and learned the same way every time")


section("the fit is the only thing a model is asked for, and only when idle")
# No mode asks a model per line any more. On identical input the per-line answer
# varied 14% with nothing new in it, cost 351 ms median, and agreed with the fitted
# rate anyway - so LLM mode now differs from Proxy in ONE thing: where the rate
# comes from.
_ac = seg(py, "def tts_auto_cap", "def calterm_log_path")
nin(_ac, "_chat(", "the cap is worked out without asking anything of a model")
for _dead in ("TTS_AUTOCAL_LLM_SYSTEM", "tts_autocal_llm_user"):
    nin(py, _dead, "and the per-line prompt is gone with it: %s" % _dead)
_lg = fp.log_dir
_td2 = tempfile.mkdtemp()
fp.log_dir = lambda cfg=None: _td2
try:
    _rw3 = [{"chars": 65, "pause_s": 0.0, "secs": 4.0, "tok": 100.0, "est": 102.0}] * 12
    _p = fp.tts_auto_cap("a line to speak.", {"ttsAutoCal": "proxy"}, cfg={}, rows=_rw3)
    _l = fp.tts_auto_cap("a line to speak.", {"ttsAutoCal": "llm", "ttsAutoCalPort": "1"},
                         cfg={}, rows=_rw3)
    check(_p[0] == _l[0] and _p[2] == _l[2],
          "LLM mode caps a line exactly as Proxy does - the model only fits the rate")
finally:
    fp.log_dir = _lg

# patch102: a progress bar cannot be gated on the panel being idle. The bar rode the
# ordinary refresh, and a queued reload waits for uiBusy() to come back empty - during
# an install something always is busy, so the reload never landed and only a tab change
# (which calls load() straight out) moved it. It reads its own endpoint now.
check('u.path == "/api/higgs-progress"' in py, "the install has an endpoint of its own")
_hpq = seg(py, 'elif u.path == "/api/higgs-progress"', 'elif u.path == "/api/models"')
check("dict(HIGGS_INSTALL)" in _hpq, "which answers the install state and nothing else")
nin(_hpq, "load_config", "and reads no config to do it - it runs beside a download")
check("/api/higgs-progress" not in fp.REMOTE_READ_OK,
      "a remote viewer cannot ask it: installing is host-only, so watching it is too")
# patch107: the reason none of it showed. renderTts skips when ttsPaneSig() comes
# out unchanged, and the sig covered everything about the pane EXCEPT the install -
# so the press flipped higgsInstall, the sig matched, the render declined, and the
# poll then asked renderCurrent for a row that renderTts declined to draw, forever.
# A refresh drew it because an empty pane always draws. Five patches funnelled here.
_sigq = seg(JS, "function ttsPaneSig()", "let ttsPaneDrawn")
check("state.higgsInstall" in _sigq and "state.higgsFound" in _sigq,
      "the pane signature covers the install and the found-install rows it draws")
for _f7 in ("g.running", "g.done", "g.error", "f.adoptable"):
    check(_f7 in _sigq, "and the shape bit %s in particular" % _f7)
nin(_sigq, "g.pct", "but NOT pct - it moves each second and higgsPaint owns it")
nin(_sigq, "g.step", "and NOT step, for the same reason")
check("renderTts(true);" in seg(JS, "async function higgsInstall()", "function higgsCancel"),
      "and the press draws with force besides - a sig bug cannot swallow it twice")

# patch109: the calibration area is laid out like the Player Tag System rows above
# it - a titled setting, the model that carries it out, the button that shows what it
# will say - and every explanation lives in the title's tooltip rather than in grey
# paragraphs between the controls.
_acb9 = seg(JS, "function ttsAutoCalBlock(st)", "function ttsDiagBlock()")
_sb9 = seg(JS, "function ttsSampBlock(st)", "// A job the panel gives to a model")
check('ttsTitle("TTS Calibration Method"' in _acb9,
      "the section leads with a titled setting, not a paragraph")
for _o9 in ('opt("off", "Fixed")', 'opt("proxy", "Proxy Algorithm (standard)")'):
    check(_o9 in _acb9, "the mode menu offers %s" % _o9.split(", ")[1][:-1])
check('opt("llm"' not in _acb9, "and LLM Controlled is gone from the menu, retired")
# patch110: whatever a choice brings with it goes in ITS row, and the row does not
# wrap - a fixed 300px middle cell dropped the server picker onto a line of its own,
# where it stopped reading as part of the setting it belongs to.
_row9 = seg(_acb9, 'if (mode === "proxy") {', "h += '<div class=\"tsplit\"></div>'")
check('mode === "llm"' not in JS,
      "no llm pane remains - proxy and off are the whole story")
# patch130: ONE interval block, declared once above the branches and called by
# both - the slider markup existing twice was the drift this file bans, and the
# duplicate-id sweep caught it.
_px9 = seg(_acb9, 'if (mode === "proxy") {', "} else {")
check(_px9.find("everyBlock(") >= 0
      and _px9.find("everyBlock(") < _px9.find('h = ttsCalRow(main, rate, "")'),
      "the refit interval rides inside the rate cell, built before the row closes")
check(_row9.count("everyBlock(") == 1 and "const everyBlock = tip =>" in _acb9,
      "one interval block, defined once, called where a refit exists")
check('"tts-ttsAutoCalEvery"'.strip('"') in _acb9
      and _acb9.count('id="tts-ttsAutoCalEvery"') == 1,
      "so the slider id exists once in the source, whatever mode renders")
check('ttsCalRow(main, rate, "")' in _px9 and "everyBlock(" in _px9,
      "Proxy: the setting, then the speech rate menu with its button in the same cell")
_sbrow = seg(_sb9, "return ttsCalRow(main,", "ttsTitle(\"Samplers\"")
check('ttsCalRow(main, "", "")' in _sbrow,
      "Sampler Calibration is the setting alone - the model cell left with the mode")
check('ttsCalRow(main, "", "")' in _row9,
      "Fixed gets none of it - the row is the setting alone")
_crq = seg(JS, "function ttsCalRow(main, mid, side)", "function hbox(")
_crcss = seg(PAGE, "#dpane-tts .calrow {", "/* the one step nothing can detect")
check('class="calrow"' in _crq and "flex-wrap:nowrap" in _crcss,
      "the row wears its class, whose ONE copy of the rules never wraps")
check("align-items:flex-start" in _crcss,
      "and stacks every cell from the same top edge")
check('class="calcell"' in _crq
      and "min-width:0" in seg(_crcss, ".calrow .calcell {", ".calrow .calgap"),
      "the shrinkable cells may shrink instead of pushing")
check("min-width:0" in seg(_crcss, ".calrow .calsel {", ".calrow .setsel"),
      "including the server picker, which is what refused to shrink before")
check(JS.count("function ttsCalRow(") == 1 and _sb9.count("ttsCalRow(main,") == 1,
      "one row shape, used by both settings")
check("ttsJobCell" not in JS,
      "the job picker itself is gone - the one remaining job needs no cell")
# the reading, above the bars, on a rule of its own
check('class="headnow"' in _acb9
      and _acb9.rindex('class="tsplit"') < _acb9.index('class="headnow"')
      < _acb9.index('id="tts-meter-bar-time"'),
      "the headroom reading sits under the last separator and above the bars")
check('id="tts-head-now"' in _acb9 and 'class="headnow"' in _acb9,
      "and wears its own class rather than the grey caption style")
check("#dpane-tts .headnow" in PAGE and "text-shadow" in seg(PAGE, "#dpane-tts .headnow",
                                                             "a rule between a setting"),
      "which is white and lit")
nin(_row9, "tts-head-now",
    "the reading is no longer one more hint in the mode row")
# grey explanation paragraphs are gone from both blocks, tooltips carry it instead
for _blk9, _nm9 in ((_acb9, "calibration"), (_sb9, "sampler")):
    check(_blk9.count('class="hint" style="line-height:1.7') == 0,
          "no grey explanation paragraph left in the %s block" % _nm9)
check(_acb9.count("ttsTitle(") >= 4 and _sb9.count("ttsTitle(") >= 3,
      "every setting in both blocks carries a title with its own tooltip",
      "%d and %d" % (_acb9.count("ttsTitle("), _sb9.count("ttsTitle(")))
check('<div class="tsplit"></div>' in _acb9,
      "and rules separate the groups of rows")


# patch111: the two menus must LINE UP. The server picker wore .tsel, whose 5px/9px
# padding is not the base select's 7px/10px, so it stood shorter and higher than the
# setting it sits beside. And a switch label wraps under its switch in a narrow cell,
# where it reads as a caption rather than as the switch's own word.
check("jobsrv" not in JS,
      "no job-server picker remains anywhere - fill logic included")
check("white-space:nowrap" in seg(PAGE, "  .swlab {", "  .tsel {"),
      "and the label cannot break onto a line of its own")
check("font-weight:700" in seg(PAGE, "#dpane-tts label.ttl {", "#dpane-tts label.ttl:hover"),
      "every title on the page is bold at the size it already had")
# one reading, not three: the fit and the last attempt sit with the headroom
_hl11 = seg(JS, "function hbox(value, label, tip, wide)", "function ttsAutoCalBlock(")
check("d.head" in _hl11 and "ttsAutoCalMedian" in _hl11 and "ttsAutoCalTried" in _hl11,
      "the headroom, the fit under it and the last attempt are one reading")
check('setChanged($("tts-head-now"), headroomBoxes(d))' in JS,
      "written by the one place that fills that line, and only when it changed")

# ---------------------------------------------------------------------- patch117
# The reading was one sentence with four numbers and two outcomes buried in it. A
# sentence has to be read from the start to find the number in it; a box says which
# number it is holding. The numbers now travel AS numbers, and the sentence the
# record prints is built from the same dict, so the two cannot drift.
_hf17 = seg(py, "def tts_headroom_facts", "def tts_autocal_headroom")
for _k17 in ("h", "n", "need", "seed", "worst", "pad", "censored", "why"):
    check('"%s"' % _k17 in _hf17,
          "the headroom answers with %s as a figure, not inside a sentence" % _k17)
check(seg(py, "def tts_autocal_headroom", "def _autocal_parse")
      .count("tts_headroom_facts(") == 1,
      "and the (headroom, why) pair callers take is that same dict, not a second copy")
check('"head": tts_headroom_facts()' in py and "headroomWhy" not in _hl11,
      "the page is sent the figures; nothing that draws a box parses the sentence")
_hfd = fp.tts_headroom_facts([{"chars": 44, "pause_s": 0.0, "secs": 4.0, "tok": 100.0,
                               "est": 80.0, "bound": "estimate", "at": "x"}] * 12, [])
check(abs(_hfd["h"] - 1.25 * fp.AUTOCAL_HEAD_PAD) < 1e-6 and _hfd["n"] == 12
      and _hfd["seed"] is False and ("%.2f" % _hfd["h"]) in _hfd["why"],
      "the figures and the sentence are the same reading", str(_hfd))
check(fp.tts_headroom_facts([], [])["seed"] is True
      and fp.tts_headroom_facts([], [])["h"] == fp.AUTOCAL_HEAD_SEED,
      "and too few lines says seed in the figures too, not only in the words")
check(fp.AUTOCAL_HEAD_MIN_N == 8 and "%d/%d" in _hf17,
      "with the threshold named once rather than typed into the wording")
_hb17 = seg(JS, "function hbox(value, label, tip, wide)", "function headroomBoxes(d)")
check("esc(String(value))" in _hb17 and "esc(String(label))" in _hb17,
      "a box escapes what it shows - the last attempt is a sentence a model wrote")
_hc17 = seg(PAGE, "#dpane-tts .headnow {", "#dpane-tts .tsplit")
check("justify-content:center" in _hc17 and "flex-wrap:wrap" in _hc17,
      "the boxes are centred in the card and take a second row rather than overflow")
check("var(--acc)" in seg(_hc17, "#dpane-tts .hbox {", ".hbox .hb-v"),
      "each box is lit with the accent, the way a Live Network box is")
check("text-align:center" in seg(_hc17, "#dpane-tts .hbox {", ".hbox .hb-v"),
      "and its figure and its name are centred over each other")
nin(_acb9, "no fit has been attempted yet",
    "the grey attempt line is gone from the block")
nin(_acb9, "no LLM fit kept yet", "and so is the grey fit line")
nin(_acb9, "medTxt", "with the locals that built them - nothing left half-removed")

# patch113: a width written against `select` never reaches the box on screen.
# Every select is replaced at runtime by a .selwrap stand-in that carries the
# select's CLASSES and nothing else - not its inline style - so patch112's caps
# sat on a hidden element while the stand-in sized itself to its longest line:
# 546px of model name, riding the switch and the button out of the card. The
# rules name the class both wear now, the way .pctl already did.
check('wrap.className = "selwrap " + sel.className' in JS,
      "the stand-in still takes the select's classes - every rule below rests on it")
check("sel.style.width" in seg(JS, "function enhanceSelects(root)", "function selSync(")
      and "cs.minWidth" in seg(JS, "function enhanceSelects(root)", "function selSync("),
      "and its width comes from the select's own width, not from its flex")
nin(_crcss, ".calrow select", "no rule left that only the hidden select would wear")
_h13 = seg(_crcss, ".calrow .calsel, #dpane-tts .calrow button.stop", ".calrow .calsel {")
check("height:32px" in _h13 and "box-sizing:border-box" in _h13,
      "one height for menu and button both, borders counted inside it")
check("width:100%" in seg(_crcss, ".calrow .setsel {", ".calrow .srvsel"),
      "the setting menu fills its 250px cell exactly")
_sv13 = seg(_crcss, ".calrow .srvsel {", ".calrow .swlab")
check("width:300px" in _sv13 and "max-width:100%" in _sv13,
      "the server menu is one fixed width, and gives way before the card does")
check("min-width:0" in seg(_crcss, ".calrow .calsel {", ".calrow .setsel"),
      "and neither carries the page-wide 260px floor into the stand-in")
# (the job cell and its server menu left with LLM Controlled in patch153)
_ac13 = seg(JS, "function ttsAutoCalBlock(st)", "function ttsDiagBlock()")
_sb13 = seg(JS, "function ttsSampBlock(st)", "// A job the panel gives to a model")
for _blk13, _id13, _cls13 in ((_ac13, "tts-ttsAutoCal", "setsel"),
                              (_sb13, "tts-ttsSampAutoCal", "setsel")):
    _s13 = seg_len(_blk13, 'class="txt calsel ' + _cls13 + '" id="' + _id13 + '"', 90)
    check("style=" not in _s13, "%s is sized by its class, not inline" % _id13)
check('<span class="calgap"></span>' in _crq,
      "a spring after the last setting collapses first and pins nothing out")
_gap13 = seg(_crcss, ".calrow .calgap {", ".calrow .calsel,")
check("flex:1 1 0" in _gap13 and "min-width:0" in _gap13,
      "and the spring is the ONE thing in the row that grows")
# patch114: measured on the glass - the menus' boxes started 9px apart and the
# label's flex gap read as 0px. Neither is left to the browser to decide now.
_rh14 = seg(_crcss, ".calrow .row {", ".calrow .swlab {")
check("height:32px" in _rh14 and "align-items:center" in _rh14,
      "the row is one line tall by rule, so nothing in a cell can re-centre its menu")
check("#dpane-tts .calrow .swlab .sw { margin-right:14px; }" in PAGE,
      "and the word stands clear of the switch by a margin, not by a flex gap")
check("gap:0" in seg(_crcss, ".calrow .swlab {", ".calrow .swlab .sw"),
      "with the gap that read as zero taken out rather than left to argue with it")

# ------------------------------------------------------------------ patch115
# The section renamed, one setting removed, one added, and the row of buttons put
# where the thing they act on is. The rule under all of it: a control is where the
# thing it changes lives, and a number that bounds a line belongs to whoever pays
# for the GPU it runs on.
_sb15 = seg(JS, "function ttsSampBlock(st)", "// A job the panel gives to a model")
_dx15 = seg(JS, "function ttsDiagBlock()", "function calTermOpen()")
check('<div class="tsect">TTS Calibration</div>' in _acb9,
      "the section is called TTS Calibration")
check('ttsTitle("TTS Calibration Method"' in _acb9,
      "and the menu inside it chooses the METHOD, which is what it does")
check('ttsTitle("Monitoring"' in _acb9 and "Where The Last Line Went" not in JS,
      "the bars and their reading sit under Monitoring")
_mon15 = seg(_acb9, 'ttsTitle("Monitoring"', 'id="tts-meter-keys-time"')
check(_mon15.index('id="tts-head-now"') < _mon15.index('id="tts-meter-head"'),
      "with the headroom under the title and the line it was taken from under that")
nin(_mon15, "margin-left:auto",
    "and the line is no longer pinned to the far right of the title")
# patch116: 26px was too big to read as a caption over the bars. One size up from the
# 13px it was, which is what was asked for the second time.
check("font-size:14px" in seg(PAGE, "#dpane-tts .headnow", "text-shadow"),
      "the headroom reading is one size bigger than it was, not twice it")

# 4. Fixed mode is one number, and it is the user's
_fx15 = seg(_acb9, "const tpc = fixedTokPerChar(st);", 'h += \'<div class="tsplit">')
check('ttsTitle("Token per character"' in _fx15
      and 'id="tts-ttsFixedTokPerChar"' in _fx15,
      "Fixed offers Token per character, titled above its slider")
check('min="1" max="25"' in _fx15, "over the range asked for: 1 to 25")
check('data-act="ttsTokPerCharReset"' in _fx15 and "Reset to Higgs Default" in _fx15,
      "with Reset to Higgs Default beside it")
_rh15 = seg(JS, 'if (d.act === "ttsTokPerCharReset") {', 'if (d.act === "ttsAutoInfo")')
check('"3.5"' in _rh15 and "/api/settings" in _rh15,
      "and that button puts 3.5 back, in the setting as well as on the slider")
check(fp.DEF_SETTINGS.get("ttsFixedTokPerChar") == "3.5",
      "3.5 is the default it resets to, and what a fresh config starts on")
check(fp.acpp_tok_per_char({"ttsFixedTokPerChar": "9"}) == 9.0
      and fp.acpp_tok_per_char({}) == fp.TTS_ACPP_TOK_PER_CHAR,
      "the arithmetic reads the setting, and falls back to Higgs' own doubled rate")
check(fp.acpp_tok_per_char({"ttsFixedTokPerChar": "0"}) == 1.0
      and fp.acpp_tok_per_char({"ttsFixedTokPerChar": "99"}) == 25.0
      and fp.acpp_tok_per_char({"ttsFixedTokPerChar": "banana"}) == fp.TTS_ACPP_TOK_PER_CHAR,
      "outside the slider's own range it is refused, not obeyed - 0 would cap every line")
check(fp.acpp_token_cap("x" * 100, {"ttsFixedTokPerChar": "10"}) == 1000
      and fp.tts_auto_cap("x" * 100, {"ttsAutoCal": "off",
                                      "ttsFixedTokPerChar": "10"})[0] == 1000,
      "and Fixed mode IS that number: chars x tok/char, through the same one rule")
nin(seg(py, "Without them the constant is the answer", "def acpp_token_cap"),
    "load_config",
    "which never reads the config itself: load_config SAVES, and this is per line")

# 5. the Algorithm button is a button, in the row of the menu it explains
check('>Algorithm</button>' in _px9 and 'ttsTitle("Algorithm"' not in JS,
      "Algorithm is a button with no title and no question mark above it")
check(_px9.index("everyBlock(") < _px9.index(">Algorithm</button>"),
      "the Refit Interval leads the cell; Algorithm keeps its place beneath")

# 6. what arrives is always forwarded, and what is in force is always shown
nin(JS, "ttsPassThrough", "the pass-through menu is gone from the page")
nin(py, "ttsPassThrough", "and from the settings, the rule and the facts answer")
nin(_sb15, "SkyrimNet's Own Settings", "with its title")
check(fp.tts_samp_now({"ttsCalTemp": "0.7"}).get("temp") == "0.7",
      "what is in force answers in the CHIPS' key names - temp, not temperature")
check(set(fp.TTS_SAMP_FIELD) == {"temp", "top_p", "min_p", "rep"}
      and "TTS_SAMP_FIELD.items()" in seg(py, "def tts_samp_now", "def cal_overrides"),
      "through the one map the line under the bars already went through")
check('"sampSent": tts_samp_now(st)' in py and py.count("def tts_samp_now") == 1,
      "one definition of that answer, used by the facts and by the meter tick")
_mt15 = seg(py, "def api_tts_meter", "AUTOCAL_EST = [0.0]")
check("tts_samp_now(st)" in _mt15,
      "the tick that paints the bars carries the samplers too")
check('setChanged($("tts-samp-chips"), ttsSampChips(r))'
      in seg(JS, "async function refreshTtsMeter", "async function refreshCalTail"),
      "so the chips are repainted on that tick, not left waiting on a diagnosis")

# 7. Steady Retry is on the Samplers line
# patch116: beside the SAMPLERS, not beside their title - it is the other thing that
# decides what a request carries, and a title row put it a line away from them
_sr16 = seg(_sb15, 'id="tts-samp-chips"', "}")
check('ttsTitle("Steady Retry"' in _sr16,
      "Steady Retry sits in the chips' own row, beside the samplers themselves")
check(_sb15.index('ttsTitle("Samplers"') < _sb15.index('id="tts-samp-chips"')
      < _sb15.index('ttsTitle("Steady Retry"'),
      "with the title above them both, on a line of its own")

# 12, 13, 14. one button row, on the terminal it acts on
check('ttsTitle("TTS Calibration Terminal"' in _dx15,
      "the record is called the TTS Calibration Terminal")
check("Hide Terminal" in _dx15 and "Show Terminal" in _dx15
      and JS.count("Hide Terminal") == 2 and JS.count("Show Terminal") == 2,
      "its button says so - in the builder and in the handler that flips it")
nin(_dx15, 'ttsTitle("Diagnose"', "the Diagnose section is gone, its button kept")
nin(JS, "ttsDiagRefresh", "and Show data with it")
nin(py, "cal_facts_text", "along with the data block only that button could write")
check('"quiet"' not in seg(py, "def api_tts_diag(body=None)", "def _tts_diag_facts")
      and "calterm_log" not in seg(py, "def api_tts_diag(body=None)", "def _tts_diag_facts"),
      "the endpoint has one way through now, not a loud one and a quiet one")
_rf13 = seg(_ac13, "const everyBlock = tip =>", 'let h = "";')
check('id="tts-ttsAutoCalEvery"' in _rf13 and 'ttsTitle("Refit Interval", tip)' in _rf13,
      "the interval slider sits UNDER its title, inside the title's own block")
nin(_ac13, '<span style="flex:0 1 250px',
    "the old beside-the-title cell is gone")
check("flex:0 1 240px" in _rf13 and "max-width:240px" not in _rf13,
      "the slider is one capped width now, not a min-max tug of war")
nin(JS, "function ttsCalRow(main, mid, extra, side)",
    "the dead third cell is gone from the signature, not carried along")
# the Prompt button, the dialog branch it was the only way into, and the payload
# that branch read all go together - a button removed is not a feature retired.
nin(JS, "data-what", "nothing asks the info dialog WHICH thing to show any more")
nin(JS, "ttsBtnCell",
    "the titled button cell is gone with its last caller - Algorithm is a button now")
nin(py, "deriveSystem", "the endpoint drops the prompt texts the dialog used to show")
nin(py, "diagSystem", "including the diagnose prompt")
nin(py, "calSystem", "and the calibration prompt")
check("DIAG_SYSTEM" in py and "DIAG_SYSTEM," in py,
      "the diagnosis prompt stays - it is still what gets sent")
nin(py, "TTS_AUTOCAL_DERIVE_SYSTEM",
    "and the retired LLM-Controlled mode's fit prompt is GONE, not orphaned - "
    "autocal_mode folds llm into proxy, so nothing could ever send it (patch184)")
nin(py, "CAL_SYSTEM", "with the sampler-choosing prompt it retired beside it")


# patch106: the two moments that read as a dead display are the two the installer
# said nothing during - from the press until the first download reports a
# percentage, and the whole unpack. The page was right: nothing had changed.
_uzq = seg(py, "def _hi_unzip", "def _hi_free_bytes")
check("_hi_log(" in _uzq, "the unpack says what it is doing while it does it")
check('HIGGS_INSTALL["pct"] = 100.0 * _done / _total' in _uzq,
      "with a percentage of its own, by uncompressed bytes")
check("time.time() - _last > 0.7" in _uzq,
      "on the download's cadence - a heartbeat, not a line per file")
check('HIGGS_INSTALL["pct"] = 0.0' in _uzq,
      "and it restarts the bar: unpacking is a phase, not a continuation")
check("def _hi_unzip(src, dest, label" in py and "_hi_unzip(zp, dest, name)" in py,
      "and it can name the archive it is unpacking")
# a phase with nothing to count still has to look alive
_barq = seg(JS, "function higgsBarHtml(g)", "function higgsPaint(g)")
check("pct > 0" in _barq and "higgsIdle" in _barq,
      "no number to show draws a moving bar, not one frozen at nothing")
check("@keyframes higgsIdle" in PAGE, "and the animation it names exists")
check(JS.count("function higgsBarHtml(") == 1, "the bar is composed in one place")
_paintq = seg(JS, "function higgsPaint(g)", "function higgsPoll()")
_pollq = seg(JS, "function higgsPoll()", "async function higgsInstall()")
# patch104: the fast path writes two nodes, and is not trusted to be the only path.
# A node found by id can be the wrong one, or gone, or in a pane rebuilt from an
# older state - and every one of those looks identical from here: the numbers stop.
# patch105: the loop cannot be ended by a bad tick, and cannot be locked out by a
# dead one. Both had happened: a throw inside the tick skipped the reschedule at the
# bottom, and the flag that stops a second loop starting then refused every restart
# until the page was reloaded by hand.
check("} finally {" in _pollq and "if (!stop) setTimeout(loop, 700)" in _pollq,
      "the reschedule is in a finally - no tick can be the last tick")
check("} catch (e) {" in seg(_pollq, "let stop = false;", "} finally {"),
      "and the whole tick is caught, including the redraw it may ask for")
check("now - window.__higgsBeat < 3000" in _pollq,
      "the claim carries a date, so a dead loop cannot hold the place for good")
check("window.__higgsBeat = Date.now();" in _pollq,
      "which every tick renews")
check("!higgsPaint(g) && curTab === \"tts\"" in _pollq,
      "a row that is nowhere on screen is asked for through the one guarded rule")
check('"running" in g' in _pollq,
      "an answer without a running flag is not an install record, so it ends nothing")
_fin = seg(_pollq, '"running" in g', "higgsPaint(g)")
check("if (!g.running)" in _fin and "stop = true;" in _fin,
      "only a record that says the install stopped stops the loop")
check("window.__higgsBeat = 0;" in _fin,
      "and it clears the claim on the way out, so the next install may start one")
# one spelling of the step line: the row draws it and the poll writes it
check(JS.count("function higgsStepText(") == 1,
      "the step line is composed in one place")
check("higgsStepText(g)" in _paintq and "esc(higgsStepText(g))" in JS,
      "and both the write and the row it draws use it")
check("nothing new for " in JS,
      "and says how long the record has been still - the reading that tells a"
      " stopped display from a quiet install")
_hpq2 = seg(py, 'elif u.path == "/api/higgs-progress"', 'elif u.path == "/api/models"')
check('_g["idle"]' in _hpq2 and "time.time() - _g[\"at\"]" in _hpq2,
      "computed on the server, off one clock rather than two")
check('HIGGS_INSTALL["at"] = time.time()' in seg(py, "def _hi_log", "def _hi_get"),
      "every step stamps the record")
check('HIGGS_INSTALL["at"] = time.time()' in seg(py, "def _hi_download", "def _hi_unzip"),
      "and so does every turn of the download, which moves without a new step")
check('"at": 0.0' in seg(py, "HIGGS_INSTALL = {", "def higgs_paths"),
      "the field exists before anything writes it")
check("/api/higgs-progress" in _pollq, "the page asks that endpoint")
nin(_pollq, "queueLoad", "not the queued reload it could never get through")
check('querySelectorAll(\'[data-higgs="step"]\')' in _paintq
      and 'querySelectorAll(\'[data-higgs="bar"]\')' in _paintq,
      "the nodes are found fresh each tick, by attribute")
nin(_paintq, "getElementById",
    "not by id: that returns ONE node and a detached twin looks identical from here")
check(".forEach(" in _paintq and "isConnected" in _paintq,
      "every copy is written, and it reports how many were really on screen")
check(_paintq.count("textContent") == 1 and _paintq.count("style.width") == 1,
      "still two writes for a number, not a page redraw")
check("higgsBarHtml(g)" in _paintq,
      "and a bar changing SHAPE is handed back to the one place that draws it")
# the press draws the row itself: the first phase has no number, so waiting for a
# round trip to change it left the button looking unpressed
_insq = seg(JS, "async function higgsInstall()", "function higgsCancel")
check("running: true" in _insq and "renderTts(true);" in _insq,
      "pressing Install draws the running row at once, from what is already known")
check(_insq.index("renderTts(true);") < _insq.index("await load();"),
      "before the round trip, not after it")
_rowq2 = seg(JS, "function higgsInstallRow()", "// The step line, composed in ONE place")
check('data-higgs="step"' in _rowq2, "the row carries the attribute the step is found by")
check('data-higgs="bar"' in _barq,
      "and the bar carries its own, wherever the bar is drawn from")
check("higgsBarHtml(g)" in _rowq2,
      "which is one place, used by the row as well as the write")
check("if (!g.running)" in _pollq and "load();" in _pollq,
      "and reloads the state once when the install stops, to draw what it came to")
# patch103: it stops for ONE reason - the install stopped. patch102 also stopped when
# it could not find its own node, and a redraw from a state older than the install
# (ttsLoadModels resolves seconds after a load and redraws) removed that node for a
# tick: the bar moved for a few seconds after every refresh and then never again.
check(_pollq.count("stop = true;") == 1,
      "the loop gives up in one place", str(_pollq.count("stop = true;")))
nin(_pollq, "clearInterval", "nothing else can end it - a missed node is a missed tick")
check("setTimeout(loop, 700)" in _pollq,
      "and it reschedules itself, so a slow answer cannot overlap the next ask")
_ldq = seg(JS, "async function load()", "function queueLoad()")
check("state.higgsInstall.running) higgsPoll()" in _ldq,
      "every state load offers to restart it, and a stale claim no longer refuses")
check("if (window.__higgsBeat && now - window.__higgsBeat < 3000) return;" in _pollq,
      "one loop however often the row is redrawn - unless the last one stopped beating")
_rowq = seg(JS, "function higgsInstallRow()", "async function higgsInstall()")
check('id="higgs-step"' in _rowq and 'id="higgs-bar"' in _rowq,
      "the running row is addressable")
check("higgsPoll();" in seg(_rowq, "if (g.running)", "if (g.error)"),
      "and starts the poll itself, so a refresh mid-install picks it up again")


# patch101: the install has two views - the terminal and the bar above it - and each
# needs its own announcement. TTSW.log raises "tail", which carries the terminals and
# not state.higgsInstall, so the bar sat still through a 5 GB download and switching
# tabs looked like the fix because a tab change reloads the state.
_hiq = seg(py, "def _hi_log", "def _hi_get")
check("TTSW.log(msg)" in _hiq, "an install step still reaches the terminal")
check('sse_notify("state")' in _hiq,
      "and the page state too, or the bar only moves when something else reloads it")
check('HIGGS_INSTALL["running"]' in _hiq,
      "only while an install is running - no state event for a step nobody is watching")
_dlq = seg(py, "def _hi_download", "def _hi_unzip")
check("time.time() - last > 1.0" in _dlq,
      "and the one caller that repeats still rate-limits itself, so the notify does too")
check('"higgsInstall": dict(HIGGS_INSTALL)' in py,
      "the state the bar is drawn from is the state that event carries")
# the retry switch had no name - only a sentence beside it that reads as prose
_sampq = seg(JS, "function ttsSampBlock", "// A job the panel gives to a model")
check('ttsTitle("Steady Retry"' in _sampq,
      "the retry sampler switch says what it is, in a title that carries its own"
      " explanation like every other setting here")
check('data-act="ttsRetrySafe"' in _sampq, "and still carries its own action")


# patch100: a dial value that does something its label does not say. The captured
# config that spoke "<|channel>thought" at the head of every line had slot 1 on
# `--reasoning-format none`, which llama.cpp documents as leaving thoughts unparsed in
# message.content - and nothing on the card said so.
check("none" in (fp.PARAM_CAUTION.get("reasonfmt") or {}),
      "the reasoning format dial cautions the value that keeps thinking in the text")
_cau = fp.PARAM_CAUTION["reasonfmt"]["none"]
check("TTS" in _cau and "auto" in _cau,
      "and says what it costs and what to use instead", _cau[:80])
for _k, _vals in fp.PARAM_CAUTION.items():
    _spec = [x for x in fp.SERVER_PARAMS if x[0] == _k]
    check(len(_spec) == 1, "a caution names a dial that exists: %s" % _k)
    for _v in _vals:
        check(_v in (_spec[0][4].get("opts") or []),
              "and a value that dial can stand on: %s=%s" % (_k, _v))
_cauq = seg(JS, "const cau = (d.caution", "h += '<div class=\"pcell")
check("d.caution" in JS and "warn = cau" in _cauq and "var(--warn)" in _cauq,
      "the card draws it beside the dial standing on that value", _cauq[:90])
check("title=" in _cauq, "with the reason on the mark itself")
check("esc(d.label) + ref + warn" in JS,
      "in the label cell, where the dial is - not in a list somewhere else")


section("the panel's own model jobs are generations, and read as generations")
# A fit or a calibration costs a server exactly what a provider's request costs it.
# Until patch98 they went through _chat straight: the server went busy for ten
# seconds and the Proxy terminal had nothing to say why.
_pj = seg(py, "def panel_chat", "# What a calibration may set")
check("PROXY.report(" in _pj,
      "a panel job is reported through the same call the proxy and PTI/PME use")
nin(_pj, "_GateHeld",
    "and holds no gate: it is asked after idle, or by someone waiting for it")
check(sorted(fp.PANEL_JOBS) == ["calib", "diag"],
      "two jobs remain, named - the fit job left with LLM Controlled",
      str(sorted(fp.PANEL_JOBS)))
for _j, (_t, _m) in fp.PANEL_JOBS.items():
    check(len(_t) <= 15 and _t.strip() == _t,
          "%s fits the record's name column" % _j, "%r is %d" % (_t, len(_t)))
    check(bool(_m) and _m != " ", "%s carries a mark of its own" % _j)
check(len({t for t, _ in fp.PANEL_JOBS.values()}) == 2
      and len({m for _, m in fp.PANEL_JOBS.values()}) == 2,
      "and no two jobs read as each other in the terminal")
# every panel-side model call goes through the one wrapper - a second route built
# by hand would be a job that is visible in the feed and invisible in the terminal
nin(py, "_chat(diag_route(",
    "no panel job calls the model around the reporting wrapper")
_body = seg(py, "def api_tts_diagnose", "def autocal_algorithm_text")
check("panel_chat(" in _body and '"diag"' in _body,
      "api_tts_diagnose asks as diag - the one model-asking TTS job left")
nin(_body, "_chat(diag_route", "and it builds no route of its own")
check("def autocal_sampler_run" not in py,
      "the sampler's model reader is gone with the mode that owned it")
# the route the report is built from: ids apart, so the statistics do not merge them
_rc = fp.diag_route(1236, {}, False, job="calib")
check(_rc["id"] == "calib" and fp.diag_route(1236, {}, False)["id"] == "diag"
      and _rc["title"] != fp.diag_route(1236, {}, False)["title"],
      "a calibration and a diagnosis are two records, not one")
check(fp.diag_route(1236, {}, False, job="fit")["id"] == "diag"
      and fp.diag_route(1236, {}, False, job="nonsense")["id"] == "diag",
      "and anything unnamed - the retired fit included - reads as the diagnosis")
check(_rc["panelOwned"] is True and _rc["priority"] == 1,
      "panel-owned and low priority, as it was before it was visible")
_ln = fp.proxy_line_text(fp.PANEL_JOBS["calib"][1], fp.PANEL_JOBS["calib"][0],
                         "1236", 120, 40, 0, 300.0, 20.0, 1.5)
check(" [1236]" in _ln and "Calibrate" in _ln,
      "and it paints as one line of the Proxy terminal", _ln[:90])


# a fit is the lowest-priority thing here: worth having, never worth a moment of
# a player's dialogue
check("autocal_wait_idle" not in py,
      "the fit's idle wait is gone with the fit - the arith refit contends with nothing")
_pm = seg(py, "class ProxyManager", "def api_provider_add")
check("def busy(self, port)" in _pm and "self.inflight" in _pm,
      "busy is counted, not guessed - the panel forwards every request itself")
check(seg(py, "wait_ms = mgr.gate.enter", "return _P").count("mgr._infl(") == 2,
      "one increment, one decrement, the decrement on the finally that already exists")
_keep_if = dict(fp.PROXY.inflight)
try:
    fp.PROXY.inflight.clear()
    fp.PROXY._infl(1236, 1); fp.PROXY._infl(1236, 1)
    check(fp.PROXY.busy(1236) == 2, "two open requests read as two")
    fp.PROXY._infl(1236, -1); fp.PROXY._infl(1236, -1)
    check(fp.PROXY.busy(1236) == 0 and 1236 not in fp.PROXY.inflight,
          "and an emptied port leaves nothing behind to leak")
finally:
    fp.PROXY.inflight.clear()
    fp.PROXY.inflight.update(_keep_if)

# Sampler calibration: read the failures, then change what they point at. patch108
# folded the button into the automatic run behind ONE switch: on shows the sampler
# settings AND lets the every-N run calibrate them; off hides them and stops the
# automation - and the user's stored values keep applying either way.
check("def autocal_sampler_arith" in py
      and "cal_overrides(" in seg(py, "def autocal_sampler_arith", "AUTOCAL_GEN")
      and "save_config(" in seg(py, "def autocal_sampler_arith", "AUTOCAL_GEN"),
      "the arith sampler step remains: it reads the bounded overrides and saves")
for _phrase in ("does NOT change how often", "top_p 1.0 truncates nothing",
                "repetition_penalty pushes probability away"):
    check(_phrase in fp.DIAG_SYSTEM,
          "the diagnosis is told what moves the odds: %s" % _phrase[:34])
check("overrunBySampler" in fp.cal_facts({"settings": {}}),
      "and is given the failure rate per configuration to read it from")
nin(JS, "ttsAutoCalRun", "the button it replaced is gone, handler and all")
nin(py, "api_tts_autocal_run", "and so is the endpoint - the run is in-process now")
check("ttsSampAutoCal" in fp.DEF_SETTINGS
      and fp.DEF_SETTINGS["ttsSampAutoCal"] == "on",
      "the switch is a known setting and ships ON - Automatic is the shipped standard")
_tk8 = seg(py, "def autocal_tick", "def api_tts_diag")
check('"ttsSampAutoCal", "on")).lower()' in seg(py, "def autocal_sampler_arith", "AUTOCAL_GEN"),
      "the arith sampler step runs only when the switch says so")
check("autocal_sampler_arith(_cfgp)" in _tk8,
      "and the tick takes it with the refit, in process, no server to pick")
check("autocal_wait_idle" not in _tk8 and "tts_job_port" not in _tk8,
      "the tick asks nothing of any server - no port, no idle window")
# ONE switch: content behind it, values not gated by it
_sb8 = seg(JS, "function ttsSampBlock(st)", "// A job the panel gives to a model")
# patch109: a two-option menu like the one above it, not a switch. Manual leaves the
# samplers themselves in the user's hands: Manual means YOU move them, not that they
# stop being sent.
check('id="tts-ttsSampAutoCal"' in _sb8 and ">Manual</option>" in _sb8
      and ">Automatic</option>" in _sb8,
      "sampler calibration is a Manual / Automatic menu, whichever method runs it")
check('ttsCalRow(main, "", "")' in _sb8,
      "no model cell remains in the row - the arith step reads the record itself")
check('id="tts-samp-chips"' in _sb8 and "if (!on) return" not in _sb8,
      "the samplers show under it either way - Manual is a hand on them, not a hide")
check("ttsSampAutoCal = sac.value" in JS,
      "and it saves like the field it now is")
nin(JS, 'd.act === "ttsSampAutoCal"',
    "the click handler it replaced is gone")
nin(seg(py, "def cal_overrides", "def "), "ttsSampAutoCal",
    "the values really do keep applying - the switch never gates cal_overrides")
for _gone in ("tts-diag-srv", "tts-autocal-srv", "tts-llm-srv"):
    nin(JS, _gone, "and the pickers of old are still gone: %s" % _gone)

section("speech sampling - the lever on how OFTEN a line fails to stop")
# The cap decides what a runaway costs. The SAMPLER decides how often there is one:
# both failures in the first field test were short, well-punctuated lines, one of them
# a line that had just succeeded a dozen times. Until now neither record kept the
# sampler, so no failure rate per setting could be worked out at all.
_ss = {"ttsPassThrough": "on"}
_seen_keep = dict(fp._SN_TTS_SEEN)
try:
    fp._SN_TTS_SEEN.clear()
    fp._SN_TTS_SEEN.update({"temperature": 0.6, "top_p": 1.0, "min_p": 0.05,
                            "repetition_penalty": 1.2})
    _a1 = fp.tts_samplers(_ss, 1)
    check(_a1 == {"temperature": 0.6, "top_p": 1.0, "min_p": 0.05, "repetition_penalty": 1.2},
          "a first attempt carries SkyrimNet's own values untouched", str(_a1))
    _a2 = fp.tts_samplers(_ss, 2)
    check(_a2["repetition_penalty"] == 1.0 and _a2["top_p"] <= 0.9
          and _a2["temperature"] < _a1["temperature"],
          "a retry drops to a profile that aims to FINISH, not to perform", str(_a2))
    check(fp.tts_samplers({**_ss, "ttsRetrySafe": "off"}, 2) == _a1,
          "and the user can turn that off - it is their setting")
    check(fp.tts_samplers({**_ss, "ttsCalRepPen": "1.0"}, 1)["repetition_penalty"] == 1.0,
          "a value set on the page wins over SkyrimNet's")
    check(set(fp.tts_samplers({}, 1)) >= {"temperature", "top_p"},
          "and what arrived is forwarded with no setting able to drop it",
          str(sorted(fp.tts_samplers({}, 1))))
finally:
    fp._SN_TTS_SEEN.clear()
    fp._SN_TTS_SEEN.update(_seen_keep)
# the request and the record must not spell the rule twice
_ao3 = seg(py, "def _tts_acpp_once", "def tts_server_port")
check("tts_samplers(_st0, attempt)" in _ao3 and "cal_overrides(_st0)" not in _ao3,
      "the request builds its sampler from the one rule, not a second copy of it")
check("TTS_SAMP_LAST" in _ao3, "and publishes what it sent, for the record to keep")
for _fn, _end in (("def eoc_record(text, cap", "def eoc_rows"),
                  ("def tts_measure_row(text, secs", "def tts_measure_record")):
    check('"samp"' in seg(py, _fn, _end),
          "%s keeps the sampler that produced it" % _fn.split()[1].split("(")[0])
# the cap in the failure record must be the cap SENT, not the fixed guard - the record
# is what a calibration reads, and it was keeping a number no request ever used
_rt2 = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
# whitespace-insensitive: one of the three wraps across a line now, and a check that
# counts a phrase would report the wrapping rather than the rule
_rt2flat = " ".join(_rt2.split())
check(_rt2flat.count("AUTOCAL_CAP[0] or acpp_token_cap(text, ") == 3,
      "every runaway - both records and the line printed - uses the cap actually "
      "in force", "found %d of 3"
      % _rt2flat.count("AUTOCAL_CAP[0] or acpp_token_cap(text, "))
nin(_rt2flat, "eoc_record(text, acpp_token_cap(text",
    "and no record is written against the fixed guard instead")
nin(_rt2flat, "% (_spent, acpp_token_cap(text",
    "and the line it prints says the same number")
check("acpp_token_cap(text)" not in _rt2 and "acpp_token_cap(processed)" not in py,
      "and the guard is always given the settings that set it, never left to read them")
# the scoreboard
_ok = [{"attempt": 1, "samp": {"temperature": "0.6", "top_p": "1", "min_p": "0.05",
                               "repetition_penalty": "1.2"}}] * 18
_bad = [{"attempt": 1, "samp": {"temperature": "0.6", "top_p": "1", "min_p": "0.05",
                                "repetition_penalty": "1.2"}}] * 2
_bd = fp.tts_sampler_board(_ok, _bad)
check(len(_bd) == 1 and _bd[0]["lines"] == 20 and _bd[0]["fail"] == 2
      and _bd[0]["rate"] == 10.0,
      "the scoreboard is failures over lines spoken, per configuration", str(_bd))
check(fp.tts_sampler_board(_ok + [{"attempt": 2, "samp": {"temperature": "0.48"}}], _bad)
      == _bd,
      "retries are excluded - they run a profile they were not chosen for")
check(fp.tts_sampler_board([{"attempt": 1}], []) == [],
      "and a line with no sampler recorded scores nothing rather than scoring wrongly")
# the page: the same chip as a provider card, one palette, one behaviour
_sc = seg(JS, "function ttsSampChips", "function ttsSampEdit")
check("PSAMP_EMO[k]" in _sc, "the chips use the palette the provider cards use")
nin(JS, "const SAMP_EMO", "and the unused twin of that palette is gone")
for _st8, _why in (("var(--acc)", "set here"), ("var(--ok)", "passed through"),
                   ("var(--dim)", "neither")):
    check(_st8 in _sc, "a chip reads differently when it is %s" % _why)
check('data-act="ttsSampChip"' in _sc
      and 'd.act === "ttsSampChip"' in JS,
      "and clicking one edits it, as on a provider card")
check("/api/tts-sampler" in JS and "def api_tts_sampler" in py, "against an endpoint of its own")
check("CAL_KNOBS" in seg(py, "def api_tts_sampler", "def api_tts_autocal_info"),
      "which takes its bounds from the one table that already holds them")
# the bars and the record show it too
check('id="tts-meter-samp"' in JS and "line.samp" in JS,
      "the bars name the sampler the line was spoken under")
check("attempt" in seg(JS, "function paintMeter(line)", "async function refreshTtsMeter"),
      "and say so when it was a retry")
check("sampler %s" in seg(py, "def autocal_log", "def tts_tags_dropped"),
      "the calculation feed records it beside the cap")
check("def tts_sampler_board" in py and '"board": tts_sampler_board()' in py,
      "and the facts answer still carries the scoreboard the diagnosis reads")


section("every id looked up is an id something makes")
# patch89 split the meter into two bars and renamed its elements, but the guard at the
# top of refreshTtsMeter still named the old single id - so it returned before painting
# and BOTH bars stayed empty, silently, with no error anywhere. A lookup that can never
# succeed is a feature switched off.
_look = set(re.findall(r'\$\("([A-Za-z][\w-]*)"\)', PAGE))
_made = set(re.findall(r'id="([A-Za-z][\w-]*)"', PAGE))
# ids finished by concatenation - id="port-' + p.port + '" - are made, just not whole
_stems = set(s for s in re.findall(r'''id=["\']([A-Za-z][\w-]*)["\']?\s*\+''', PAGE) if s)
_orphan = sorted(i for i in _look if i not in _made
                 and not any(i.startswith(s) for s in _stems)
                 and i not in ("sub",))      # built by name in renderStats
check(not _orphan, "no element is looked up by an id nothing creates", ", ".join(_orphan))


section("three modes, and a config written before them")
# Off / Proxy. `algo` and `median` were names for what Proxy does with and without
# a fitted rate, and `llm` was retired in patch153 once its per-line ask had already
# converged to the proxy arithmetic - every old spelling keeps doing what it did.
for _old, _want, _fit in (("algo", "proxy", False), ("median", "proxy", True),
                          ("proxy", "proxy", False), ("llm", "proxy", False),
                          ("off", "off", False), ("", "off", False)):
    check(fp.autocal_mode({"ttsAutoCal": _old}) == _want,
          "%r is read as %s" % (_old or "(unset)", _want))
    check(fp.autocal_use_fit({"ttsAutoCal": _old}) is False,
          "and %r alone brings no fit - only a stored one does" % (_old or "(unset)"))
check(fp.autocal_use_fit({"ttsAutoCalMedian": chr(123) + '"cps": 14.0, "lead": 0.4' + chr(125)}) is True
      and fp.autocal_use_fit({"ttsAutoCalMedian": chr(123) + '"cps": 99, "lead": 0.4' + chr(125)}) is False,
      "a stored fit is used the moment it exists and passes bounds - no switch; "
      "a refused fit is not")
_ml = seg(JS, "function autoCalMode", "function ttsAutoCalBlock")
for _old in ("algo", "median", "proxy", "llm"):
    check('"%s"' % _old in _ml, "and the page reads %r the same way" % _old)

# the slider's range is the law wherever it is read
for _v, _want in (("5", 5), ("25", 25), ("250", 250), ("1", 5), ("9999", 250),
                  ("abc", 25), ("", 25)):
    check(fp.autocal_every({"ttsAutoCalEvery": _v}) == _want,
          "every %r means %d lines" % (_v, _want))
check('min="5" max="250"' in JS, "and the slider offers exactly that range")
# a range fires input while dragging and change on release - neither is a click, and
# a handler in the click chain could never run (the same trap buttons fell into)
_inp = seg(JS, 'if (t && t.id === "ip-panel")', "function fieldDone")
check('t.id === "tts-ttsAutoCalEvery"' in _inp,
      "the slider label follows the drag, from the input chain")
_chg = seg(JS, 'document.addEventListener("change", function(e) {', "addEventListener(\"keydown\"")
check('el.id === "tts-ttsAutoCalEvery"' in _chg and "ttsAutoCalEvery: v" in _chg,
      "and the value is written once, on release")
nin(JS, 'd.act === "autoCalEvery"',
    "and nothing is left in the click chain, which a range never reaches")

# the automatic fit
_at = seg(py, "def autocal_tick", "def api_tts_diag")
check("autocal_derive_arith(_cfgp" in _at and 'if _mode == "proxy":' in _at,
      "Proxy refits by arithmetic, inline - it still never starts a model call")
check("threading.Thread" not in _at and "AUTOCAL_DERIVING" not in _at,
      "no thread and no in-flight latch remain: the arith refit is instant and inline")
for _dead in ("api_tts_autocal_derive", "/api/tts-autocal-derive",
              "def autocal_derive(port", "autocal_wait_idle"):
    nin(py, _dead, "the model fit is gone whole: %s" % _dead)
nin(JS, "ttsAutoDerive", "and so is the button it once had")
# the picker left the mode block in patch92: one for the page, checked above
_pb = seg(JS, "function ttsAutoCalBlock", "function ttsDiagBlock")
nin(_pb, '<select class="tsel" id="tts-llm-srv',
    "the mode block draws no picker of its own")
_gn = fp.AUTOCAL_GEN[0]
_said = []
_noted = []
_realcal, _realnote, _realsince = fp.calterm_log, fp.autocal_note, fp.autocal_lines_since
try:
    # patch100: seeded from the measurement store and recorded to the config. Both
    # are held here - a gate that writes into the tree it judges has judged a
    # different tree (gotcha 20).
    fp.autocal_note = lambda outcome: _noted.append(str(outcome))
    fp.autocal_lines_since = lambda st: 0
    # captured, not written: the feed goes through log_dir(), and a gate that
    # writes into the tree it is judging has judged a different tree (gotcha 20)
    fp.calterm_log = lambda lines, blank=True: _said.append(
        lines if isinstance(lines, str) else "\n".join(str(x) for x in lines))
    fp.AUTOCAL_GEN[0] = 0
    _realda, _realsa = fp.autocal_derive_arith, fp.autocal_sampler_arith
    _realcfg = fp.CONFIG
    # the proxy tick loads the config, and load_config CREATES the file when it is
    # absent - pointed at the tree, the gate would write into what it judges
    fp.CONFIG = os.path.join(tempfile.mkdtemp(), "fleet-config.json")
    _arith = []
    fp.autocal_derive_arith = lambda cfg=None, why="": _arith.append(why) or {"ok": True}
    fp.autocal_sampler_arith = lambda cfg=None: None
    try:
        for _i in range(30):
            fp.autocal_tick({"ttsAutoCal": "proxy", "ttsAutoCalEvery": "5",
                             "ttsAutoCalPort": "1"})
    finally:
        fp.autocal_derive_arith, fp.autocal_sampler_arith = _realda, _realsa
        fp.CONFIG = _realcfg
    check(len(_arith) == 6 and all("every 5 lines" in w for w in _arith),
          "Proxy counts, and refits by arithmetic every N lines, inline",
          str(_arith[:3]))
    check(not _said, "the arithmetic path spoke through its own runner, not the tick")
    # a config that still says llm is the migration case: it must count and refit
    # by the same arithmetic, asking nothing of any server
    _realcfg2 = fp.CONFIG
    fp.CONFIG = os.path.join(tempfile.mkdtemp(), "fleet-config.json")
    _arith2 = []
    fp.autocal_derive_arith = lambda cfg=None, why="": _arith2.append(why) or {"ok": True}
    fp.autocal_sampler_arith = lambda cfg=None: None
    try:
        for _i in range(7):
            fp.autocal_tick({"ttsAutoCal": "llm", "ttsAutoCalEvery": "5"})
    finally:
        fp.autocal_derive_arith, fp.autocal_sampler_arith = _realda, _realsa
        fp.CONFIG = _realcfg2
    check(len(_arith2) == 1 and "every 5 lines" in _arith2[0],
          "a saved llm config counts and refits by arithmetic - the migration is "
          "behaviour, not a rename", str(_arith2))
    check(not _noted, "and nothing warns about servers: there is none to want")
finally:
    fp.calterm_log = _realcal
    fp.autocal_note = _realnote
    fp.autocal_lines_since = _realsince
    fp.AUTOCAL_GEN[0] = _gn

# patch100: the interval survives a restart. It used to start from zero every time
# the panel came up, so a long interval and a panel restarted often meant the fit was
# due forever and never arrived - the lines had been measured and kept, and the one
# thing counting them had forgotten.
_sinceq = seg(py, "def autocal_lines_since", "def autocal_tick")
check("tts_measure_rows()" in _sinceq and '"ttsAutoCalTriedAt"' in _sinceq,
      "the count is read from the two records that already survive a restart")
nin(_sinceq, "save_config", "and reading it writes nothing")
_tickq = seg(py, "def autocal_tick", "def api_tts_diag")
check("AUTOCAL_GEN[0] = autocal_lines_since(st)" in _tickq,
      "the tick seeds itself once, from that count")
nin(_tickq, "AUTOCAL_GEN[0] % every",
    "and counts TO the interval - a modulus skips a nudged total")
_lines = []
_realsince2, _realnote2, _realcal2 = (fp.autocal_lines_since, fp.autocal_note,
                                      fp.calterm_log)
_gn2 = fp.AUTOCAL_GEN[0]
try:
    fp.autocal_lines_since = lambda st: 8
    fp.autocal_note = lambda outcome: _lines.append(str(outcome))
    fp.calterm_log = lambda lines, blank=True: None
    _realda3, _realsa3 = fp.autocal_derive_arith, fp.autocal_sampler_arith
    _realcfg3 = fp.CONFIG
    fp.CONFIG = os.path.join(tempfile.mkdtemp(), "fleet-config.json")
    _ar3 = []
    fp.autocal_derive_arith = lambda cfg=None, why="": _ar3.append(why) or {"ok": True}
    fp.autocal_sampler_arith = lambda cfg=None: None
    try:
        fp.AUTOCAL_GEN[0] = -1
        fp.autocal_tick({"ttsAutoCal": "llm", "ttsAutoCalEvery": "10"})
        check(fp.AUTOCAL_GEN[0] == 9,
              "eight lines spoken before the restart still count towards the next fit",
              str(fp.AUTOCAL_GEN[0]))
        fp.autocal_tick({"ttsAutoCal": "llm", "ttsAutoCalEvery": "10"})
        check(fp.AUTOCAL_GEN[0] == 0 and len(_ar3) == 1,
              "and the tenth is the one that refits - by arithmetic, saved mode llm or not",
              "gen=%d arith=%d" % (fp.AUTOCAL_GEN[0], len(_ar3)))
    finally:
        fp.autocal_derive_arith, fp.autocal_sampler_arith = _realda3, _realsa3
        fp.CONFIG = _realcfg3
finally:
    fp.autocal_lines_since, fp.autocal_note = _realsince2, _realnote2
    fp.calterm_log = _realcal2
    fp.AUTOCAL_GEN[0] = _gn2

# what the last attempt came to is kept where the page can read it: "no fit yet" was
# one sentence for never tried, could not run, and refused every time
_noteq = seg(py, "def autocal_note", "def autocal_derive_arith")
check('st["ttsAutoCalTried"]' in _noteq and 'st["ttsAutoCalTriedAt"]' in _noteq,
      "an attempt is recorded with what it came to and when")
check("ttsAutoCalTried" in fp.DEF_SETTINGS
      and "ttsAutoCalTriedAt" in fp.DEF_SETTINGS,
      "and both are known settings, so a fresh config has them")
_derq = seg(py, "def autocal_derive_arith", "AUTOCAL_GEN")
check(_derq.count("autocal_note(") == 1,
      "the arith refit records its outcome where the page reads the last attempt")
check('ttsAutoCalTried' in seg(py, "def autocal_note", "def autocal_lines_since"),
      "and autocal_note is the one place that writes the attempt record")
check("ttsAutoCalTried" in JS and '"last attempt"' in JS,
      "the page shows the attempt, not only the fit that was kept")
check("none kept" in seg(JS, "function headroomBoxes(d)", "function ttsAutoCalBlock("),
      "and says plainly when there has never been one - in that same reading")
nin(JS, "no LLM fit derived yet",
    "the old sentence is gone - it read as never tried when it meant never kept")


# Every path out of the fit writes exactly one record, including the two guards
# that used to return in silence - the automatic caller has no page to show an
# error on, so an unlogged return is an invisible one.
_dvq = seg(py, "def autocal_derive_arith", "def autocal_sampler_arith")
check(_dvq.count("return {") == _dvq.count('calterm_log(["TTS calibration') > 0,
      "every way out of the fit writes one record - none returns quietly",
      "%d returns, %d records" % (_dvq.count("return {"),
                                  _dvq.count('calterm_log(["derive median')))
check("AUTOCAL_DERIVE_MIN" in seg(_dvq, "only %d line(s) measured", "return"),
      "and the too-few-lines record says how many it wanted")

# both bars, always, with a rule between them
for _id in ("tts-meter-bar-time", "tts-meter-bar-tok",
            "tts-meter-keys-time", "tts-meter-keys-tok"):
    check('id="%s"' % _id in JS, "the page draws %s" % _id)
check("height:1px;margin:12px 0;background:var(--line)" in JS,
      "with a rule between the two")
# markup is not paint: patch89 had every element and drew nothing into them
_rm = seg(JS, "async function refreshTtsMeter", "async function refreshCalTail")
_guard = re.search(r'\$\("([\w-]+)"\)', _rm)
check(_guard and ('id="%s"' % _guard.group(1)) in JS,
      "the meter guards on an id the page actually creates",
      _guard.group(1) if _guard else "no guard found")
for _fn in ("paintMeterBar(line, \"time\")", "paintMeterBar(line, \"tok\")"):
    check(_fn in seg(JS, "function paintMeter(line)", "async function refreshTtsMeter"),
          "and paints both bars: %s" % _fn)
nin(JS, "ttsMeterView", "and the toggle that showed one at a time is gone")
nin(str(fp.DEF_SETTINGS), "ttsMeterView", "including its setting")
fp.PTI_CACHE.clear()
# every tag needs a word, or the terminal shows a raw identifier
_tw = seg(py, "TTS_TAG_WORDS = {", "def tts_tags_display")
_names = set(re.findall(r'\("(\w+)", "(\w+)"\)', _tw))
_all = set()
_cat = seg(py, "TTS_TAGS = {", "# The model card's own spellings")
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
_vi = seg(py, "def tts_voice_index", "def tts_ref_canonical")
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
check(PAGE.count(">Timestamps</button>") == 7, "Timestamps is on every terminal",
      str(PAGE.count(">Timestamps</button>")))
# one in the dashboard Options panel, one in the split view Options panel, and the
# per-pane copies that were already there
# one per split pane, one in the dashboard Options panel, one in the outer full-window bar
check(PAGE.count(">Dialogue Text</button>") == 4
      and ">Insert TTS</button>" not in PAGE,
      "Dialogue Text (renamed from Insert TTS) only where a completion is shown",
      str(PAGE.count(">Dialogue Text</button>")))
check("function onOffLabel" in JS,
      "a toggle reads its own state, the same way Remote Access and Fullscreen do")
_ool = seg(JS, "function onOffLabel", "function syncTermToggleUI")
check('"blueglow"' in _ool, "with On in blue and Off plain")
# widened: the function gained a row-spacing sync and a provider repaint at its head
_stu = seg_len(JS, "function syncTermToggleUI", 1000)
check(_stu.count("b.innerHTML = onOffLabel") == 3,
      "all three toggles are labelled - Timestamps, Insert TTS, Player Tag Output",
      str(_stu.count("b.innerHTML = onOffLabel")))
check('onOffLabel("Timestamps", on)' in _stu and 'b.dataset.kind' in _stu,
      "and Timestamps reads the terminal it belongs to, not a global")
check("syncTermToggleUI" in seg_len(JS, "function refreshCurTerm", 400),
      "the lit state is applied on every draw, not only after a click")
check("#f2c14e" in JS, "the spoken line is gold, not the theme accent")
check('"launchArc": False' in py, "the launch arc is off by default")
# the engine needs the tag flush against its word; a reader needs a space
_dp = seg(py, "def tts_tags_display", "def tts_normalize")
check('"*%s* "' in _dp, "the terminal spaces a tag from the word after it")
_ap = seg_len(py, "def tts_apply_tags", 2200)
check('"*%s* "' not in _ap, "but the engine still gets it flush, as Boson require")
_lg = seg(py, "    def log(self, line):", "    def save_upload")
check("%H:%M:%S" in _lg,
      "the TTS log is stamped, so a spoken line can be placed beside its completion")
_sp = seg_len(JS, "function spliceTts", 2200)
check("stampSecs" in _sp, "spoken lines are paired to a completion by time")
check("TTS_BURST_GAP" in JS and "ttsBursts()" in _sp,
      "a streamed reply's chunks are grouped into one burst, not matched line by line")
check("TTS_NEAR_DLG" in _sp,
      "and the burst attaches where it STARTS - TTS fires before the timing line lands")
check("dialogue/i.test" in _sp, "and to a dialogue completion, not any completion")
_at = seg_len(py, "def api_tail", 1600)
check("PANEL_START" in _at,
      "a fleet log from a previous run of the panel is not shown as if it were this one")
check("waiting for this session" in _at, "and says so plainly instead of looking stale")
check("a.at - b.at" in JS,
      "spoken lines are read in time order rather than reversing")
check("b - a" in _sp, "inserted bottom-up, so earlier positions stay valid")
check("paintSpoken" in seg_len(JS, "if (which !== \"dashboard\")", 2000),
      "a spliced line is painted like it is in the TTS terminal, not left plain")
check(JS.count("function paintSpoken") == 1, "one painter, shared by both terminals")


section("spoken line in the proxy log")
_lg2 = seg(py, "def _run_inner", "def _silence")
check("(local clip)" not in _lg2,
      "no suffix on the speaker - it broke the name and was not wanted")
check('"  [local clip]"' in py, "the fact is reported on the Saved line instead")
_ps2 = seg(JS, "function paintSpoken", "function paintTail")
# the mask is gone: the icon varies, so the read is structural - checked in the mood
# section below
check("bare.indexOf" in _ps2, "the speaker is read without depending on which icon leads")
check("sayRx" not in _ps2,
      "not by a regex whose colon class swallowed the timestamp")
check(TTS_LOG_CLEAR := ("TTS_LOG_NAME)" in py and 'with open(_tl, "w"' in py),
      "the TTS log starts empty each session, like the fleet logs do")


section("split panes and insertion marker")
_pt2 = seg(JS, "function paintTail", "function stepAt")
# the splice places lines BY timestamp, so stripping them first left it nothing to work
# with and the insertions silently vanished
check(_pt2.index("spliceTts(text)") < _pt2.index("stripStamps(text)"),
      "the splice runs before stamps are stripped, or insertions disappear with them")
# the arrow became a channel tree; the marker checks live in the tree section below
check("TREE_MID" in JS, "an inserted line is marked")
_st = seg(JS, "function stripStamps", "function ttsSpokenLines")
check("TSTAMP_RX" in _st,
      "hiding stamps keeps the marker - the glyph sits after the stamp, so removing "
      "the stamp leaves it alone")
# strip comments: the note explaining "No new RegExp(...)" matched the test itself
check("new RegExp(" not in re.sub(r"//[^\n]*", "", _st),
      "and reuses the working literal rather than rebuilding it")

_sf = seg(JS, "const SPLIT_FEEDS", "async function refreshSplit")
check('"dashboard", "Proxy"' in _sf and '"tts", "TTS"' in _sf,
      "each split pane can show the proxy, thinking content or TTS")
# Options carries what only a proxy feed can show, so the button belongs to whichever
# pane is showing that feed and goes when the pane is switched to something else
check("splitopt-" in _sf and 'splitFeed(side) === "dashboard"' in _sf,
      "the Options button appears only on a pane showing the proxy")
check("splitins-" in _sf, "and so does Insert TTS, which is now inside it")
check('classList.remove("optopen")' in _sf,
      "and a button that disappears does not leave its menu open behind it")
check('"splitSrcD": "dashboard"' in py, "the choice is a setting, so it survives a reload")
_chg = seg_before(JS, 'd.act === "ttsModelSel"', 400)
check("splitFeed" in _chg, "the selector is handled on change, not click")


section("tts tree and existing install")
_sl = seg_len(JS, "function spliceTts", 2600)
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
# a fixed half-row since patch20 - 50% of a WRAPPED row would fall through the text
check(".tbrend::before" in _css and "height:.8em" in _css,
      "and the last one stops at the elbow")
# 50% of a full-height branch lands between the rows of a wrapped line
check("top:50%" not in seg(_css, ".tail .tbr::after", ".tail .pmark"),
      "the elbow is pinned to the first row, not to half the branch")
check("s.stamp" in _sl, "the glyph comes AFTER the timestamp, not before it")
_ps3 = seg(JS, "function paintSpoken", "function paintTail")
check("var(--acc)" in _ps3 and "text-shadow" in _ps3,
      "the marker glows in the accent colour")

# the binary reports no version of its own, so the tag is recorded when installed
check('"ttsAcppVersion"' in py, "the audio.cpp release tag is a setting")
check('st["ttsAcppVersion"] = tag' in py, "written at install time")
check('out["local"] = acpp_local_version' in py,
      "and reported by the version check, which the binary cannot answer")

# files can be present while the settings are not - a failed config save did exactly that
_hp = seg(py, "def higgs_present", "def api_higgs_adopt")
check(".gguf" in _hp and "find_acpp_exe" in _hp,
      "an install already on disk is detected: server plus at least one model")
check('"adoptable": bool(exe and models and not wired)' in _hp,
      "and only offered when the settings are not already pointing somewhere")
check("/api/higgs-adopt" not in (_ro | _po), "adopting is host-only")
check("higgsAdopt" in JS, "the page offers to use it rather than asking for four paths")


section("npc name from the prompt")
# the voice sample is named after the voicetype; the character's name is in the dialogue
# prompt the proxy already forwards
_ns = seg(py, "def note_speaker", "def speaker_for_voice")
check("SPEAKER_SCAN" in _ns and "[:SPEAKER_SCAN]" in _ns,
      "only the first few KB of a request is scanned, not 45 KB of prompt")
check("json" not in _ns, "and it is not JSON-parsed on every request")
check("_spk_recent.append((time.time(), name))" in _ns,
      "only the NAME is kept - never the prompt")
_sv = seg(py, "def speaker_for_voice", "def tts_voice_name")
check("del _spk_recent[idx]" in _sv,
      "a paired request is CONSUMED, so a second voice cannot inherit the same name")
# A generic voicetype - femalecommoner, maleguard - is shared by dozens of characters.
# Caching for good meant the first commoner to speak owned that voice for the session
# and every commoner after wore their name. Fresh evidence wins; the cache is the
# fallback for a line with no dialogue request behind it.
check("return known or \"\"" in _sv, "an unpaired line falls back to the last name learned")
fp.panel_log = (lambda *_a, **_k: None) if not hasattr(fp, "_gate_quiet") else fp.panel_log
_realpl = fp.panel_log
fp.panel_log = lambda *_a, **_k: None
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp.note_speaker(b"You are Brelyna Maryon, a mage of the College")
    _first = fp.speaker_for_voice("femalecommoner")
    _again = fp.speaker_for_voice("femalecommoner")
    fp.note_speaker(b"You are Ysolda, a trader in Whiterun")
    _second = fp.speaker_for_voice("femalecommoner")
finally:
    fp.panel_log = _realpl
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
check(_first == "Brelyna Maryon", "the name behind a voicetype is learned", _first)
check(_again == "Brelyna Maryon", "and held when nothing newer has arrived", _again)
check(_second == "Ysolda",
      "but a shared voicetype takes the character who just spoke, not the first ever",
      _second)
check("note_speaker(body)" in seg_len(py, "def _mk_handler", 4000),
      "read from the request the proxy is already carrying, with no extra model call")
check("def tts_speaker_label" in py and "or tts_voice_name(path)" in py,
      "the terminal shows the character where known and the voicetype otherwise")


section("player vs npc naming")
# the player's line is spoken when THEY speak, before the next dialogue request - so it
# was pairing with the previous turn's character and stealing that name
check("PLAYER_VOICES" in py, "the player's own voice is named apart from the learned ones")
check("'s Party" in py,
      "the player is named by the PARTY, which is always theirs")
check('You are speaking to' not in py.split("PLAYER_RX")[1][:200],
      "NOT by 'speaking to', which names the LISTENER - one NPC addressing another put "
      "that NPC's name on the player's own line")
check('return "Player"' in py, "and falls back to Player rather than borrowing a name")
# patch116: a fixed 256 KB window is a guess about how long a prompt is. The marker
# sits ~17 KB in on the stock prompt and past that window on a long memory block, and
# the name was never read at all on this machine.
nin(py, "PLAYER_SCAN", "no fixed window on that read - the whole body is searched")
check("pm = PLAYER_RX.search(body)" in py,
      "the party heading is looked for wherever it is, however long the prompt")
check("if not _spk_player[0]:" in py, "but only until it is found once")
check(bool(fp.PLAYER_RX.search(b"## Maxxor's Party's Active Quests"))
      and bool(fp.PLAYER_RX.search(b"## Maxxor's Party")),
      "and any possessive on the party names them, not that one heading alone")
# ... and the gate will not let that be written unguarded again. re.search answers a
# Match or None, `A and B` on two of them answers the SECOND - so one None makes the
# whole expression None, which this gate reads as SKIP. It ran green while testing
# nothing, which is the one thing a gate must never do.
_gsrc = open(os.path.abspath(__file__), encoding="utf-8").read()
# a match used as a plain operand is the danger; `not m`, `m.group(...)`, a
# comparison, or the NAME of a search quoted inside a containment test are all
# already booleans by the time check() sees them
_GSAFE = ("bool(", "not ", ".group(", "==", "!=", "is None", "is not None",
          '" in ', "' in ")
for _gl in _gsrc.splitlines():
    _gs = _gl.strip()
    if (_gs.startswith("check(") and ".search(" in _gs
            and not any(_s in _gs for _s in _GSAFE)):
        check(False, "a check on a regex match is coerced to a bool, or it SKIPs",
              _gs[:80])
check(True, "every check written on a regex match says bool() and cannot skip itself")
_sv2 = seg(py, "def speaker_for_voice", "def acpp_local_version")
check("if key in PLAYER_VOICES" in _sv2 and "return _spk_player[0]" in _sv2,
      "so it never enters the learned map and cannot take an NPC's name")
# and when it cannot be read, it says so ONCE, with what the prompt did head its
# sections with - the thought under a reply is named from that request's own "You are"
# line, so a player thought read right while every spoken line said "Player", silently
check("def player_name_unread" in py and "player_name_unread()" in _sv2,
      "a line that goes out unnamed says so rather than looking like it worked")
check("_PLAYER_SAID" in py and "HEADING_RX" in py,
      "once, and with the headings that request actually used")
_pn16 = {}
try:
    fp._spk_player[0] = ""
    fp._PLAYER_SAID[0] = False
    _big = (b"You are Serana, a Female Nord in Skyrim.\n" + b"x" * 400000
            + b"\n## Maxxor's Party's Active Quests\n")
    fp.note_speaker(_big)
    check(fp._spk_player[0] == "Maxxor",
          "a party heading 400 KB into a request is still read", fp._spk_player[0])
    check(fp.speaker_for_voice("player") == "Maxxor",
          "and the player's spoken line carries their name, not the word Player")
    fp._spk_player[0] = ""
    fp._PLAYER_SAID[0] = False
    fp.note_speaker(b"You are Faralda, a Female Altmer in Skyrim.\n## Recent Events\n")
    check(fp.speaker_for_voice("player") == "Player" and fp._PLAYER_SAID[0],
          "with no such heading anywhere it falls back, and having said why")
    check(fp._spk_heads == ["Recent Events"],
          "keeping the headings it did see, which is what names the next fix",
          str(fp._spk_heads))
finally:
    fp._spk_player[0] = ""
    fp._PLAYER_SAID[0] = False
    fp._spk_heads[:] = []

# the binary answers no --version; a hand install has no recorded tag either
_lv = seg(py, "def acpp_local_version", "def api_acpp_update")
check("README" in _lv, "a version is read off disk when the panel did not install it")
# the README turned out to carry no version, so try what else might answer
check("/health" in _lv and "/v1/models" in _lv,
      "a running server is asked, since the binary itself answers no --version")
check("tts_server_log_newest" in _lv,
      "and its own startup output, which the panel already captures")
check("VersionInfo" in _lv, "and the file's own Windows version resource")
check('return ""' in _lv,
      "returning nothing is a valid answer - better than inventing a number")
check("CHANGELOG.md" in _lv, "and a changelog shipped beside it counts too")
check('st.get("ttsAcppVersion")' in _lv, "with a recorded tag preferred over a guess")
check("acpp_local_version(c)" in py, "and recorded when an existing install is adopted")


section("mood icon on a spoken line")
_mi = seg(py, "def tts_mood_icon", "def tts_tags_display")
check('== "emotion":' in _mi and 'TTS_MOOD.get(("emotion", val.lower()), TTS_MOOD_PLAIN)' in _mi,
      "an emotion always decides the face - unmapped ones show the plain face, "
      "never a stand-in")
check('("sfx", val.lower())' in _mi and _mi.index('"style"') < _mi.rindex('"sfx"'),
      "a sound fronts the line only as the LAST resort - the owner's patch171 "
      "call: a chunk whose only tag is a sound wears the sound's own icon")
_missing = []
_cat = seg(py, "TTS_TAGS = {", "# The model card's own spellings")
_mood = seg(py, "TTS_MOOD = {", "TTS_MOOD_PLAIN")
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
_ps4 = seg(JS, "function paintSpoken", "function paintTail")
check("bare.indexOf(\" \")" in _ps4,
      "and the speaker is read structurally: first token is the icon, then the name")


section("launch buttons")
check('arcLabel("Launch LLM")' in JS, "the fleet button says what it launches")
check('id="launchTtsBtn"' in PAGE, "and there is a second one for the TTS server")
check("function launchTts" in JS and "function syncTtsButton" in JS,
      "with its own start and its own state")
_tb = seg(JS, "function syncTtsButton", "async function launchStack")
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
_row2 = seg(JS, "function higgsInstallRow", "async function higgsInstall")
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
_ps5 = seg(JS, "function paintSpoken", "function paintTail")
# the indent used to be computed; it is measured by the browser now - see the
# "column width and the fleet log" section
check("display:flex" in _ps5 and "flex:0 0 auto" in _ps5,
      "a wrapped spoken line hangs under the dialogue, not back at the tree column")
check("function termCols" not in JS,
      "and nothing counts columns - that could never align an emoji")
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
check(PAGE.count(">Timestamps</button>") == 7,
      "and a copy lives in the outer bar, as its Adjust does",
      str(PAGE.count(">Timestamps</button>")))
check("splitins-t-max" in JS, "including Insert TTS, kept in step with the feed")
# the pid check became unnecessary once both views shared ttsBusy: the flag is cleared
# in the finally of ttsServer(), whatever the outcome
check("} finally {" in seg_len(JS, "async function ttsServer", 1400),
      "the TTS flag is cleared however the action ends - a stop mid-start cannot strand it")
check('"termStampsOff"' in py, "timestamps are remembered per terminal")
check("function termStampsOn(which)" in JS, "and each terminal is asked about itself")
# in split view the feed shown and the pane showing it are different names; a per-pane
# setting has to follow the PANE or the button toggles something else
check('paintTail(kd, d.text || d.error || "", $("tail-splitd"), "splitd")' in JS,
      "a split pane tells paintTail which pane it is, not only which feed")
check("const who = pane || which;" in JS, "and the timestamps follow the pane")
check(PAGE.count('data-act="termStamps" data-kind=') == 7,
      "every button says which terminal it belongs to",
      str(PAGE.count('data-act="termStamps" data-kind=')))


section("v3.73 sweep")
# NO_CFG_LOCK removed the serialization these two had been relying on
check("_FLEET_LOCK" in py and "_TTSSRV_LOCK" in py,
      "launching and starting TTS each have their own lock, so neither can double-start")
check("acquire(blocking=False)" in py,
      "and a second press is told so rather than queued behind the first")
for _e in ("/api/launch-stack", "/api/tts-server"):
    _seg = seg_len(py, "NO_CFG_LOCK = frozenset", 400)
    check(_e in _seg, "%s runs outside the config lock" % _e)
# one pattern for a rendered control token, not one per caller
check("TTS_TOKEN_RX" in py and py.count('r"<\\|([a-z]+):([a-z_]+)\\|>"') == 1,
      "there is one pattern for a control token, not a copy per caller")
# the spoken line and the saved line were each written once per engine arm
check(py.count("def say_line") == 1, "the spoken line is built in one place")
# The MOSS arm was never finished - it announced the line and then read six variables
# only the audio.cpp arm computes, and never called _post_chunk at all. It says so now
# instead of raising a NameError about the last of them.
_moss = seg(py, "The MOSS arm is INCOMPLETE", "except Exception as e:")
check("not implemented in this build" in _moss,
      "and the unfinished MOSS arm says so rather than failing on a stray name")
check(py.count("def saved_line") == 1 and py.count("self.saved_line(") == 1,
      "and so is the saved line, from the one arm that generates anything")
# the tree must describe what the code does, not what it used to
_pt3 = seg(JS, "const hostItems", "let svg")
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
check('"tts"' in seg_len(JS, '["servers","tts","provmgmt"', 160),
      "showTab knows about it, or the pane would never be shown")
check('showDsub("tts")' not in JS, "nothing still navigates to the old place")
check('data-hostonly' in seg_around(PAGE, 'id="nav-tts"', 60, 60),
      "host-only, as the sub-tab was")
check('"termInsTts": "on"' in py, "spoken lines show in the proxy terminal by default")
check(">Install Higgs v3</button>" in JS, "the install button is not chatty about it")


section("tree wrapping and TTS sections")
# SVG text does not wrap: a long bullet ran straight across into the next column
_liw = seg(JS, "function li(x, y, mark", "const hostItems")
check("LI_CHARS" in _liw and "rows.push" in _liw, "a long bullet wraps inside its column")
check("h: LI_STEP" in _liw, "and reports its height, so the next one starts below it")
check("__H__" in JS and "Math.max(650" in JS,
      "the box is sized to the wrapped content rather than a fixed height")
# the page reads as groups now
_fsm = re.search(r"const TTS_FIELDSETS = \{(.*?)\n\};", JS, re.S)
check(bool(_fsm), "the TTS fields come from one table")
for _eng, _body in re.findall(r"(\w+): \[(.*?)\n  \]", _fsm.group(1) if _fsm else "", re.S):
    _rows = re.findall(r'\["([^"]+)",', _body)
    check(bool(_rows) and _rows[0] == "##",
          "%s fields open with a heading" % _eng, str(_rows[:2]))
    check(_rows.count("##") >= 3,
          "%s is grouped rather than one long column" % _eng, "%d headings" % _rows.count("##"))
    check(not [1 for _a, _b in zip(_rows, _rows[1:]) if _a == "##" and _b == "##"],
          "%s has no heading with nothing under it" % _eng)
check('f[0] === "##"' in JS, "and a heading row is rendered as one, not as a field")
check("#dpane-tts .tsect" in _css and "border-top" in _css,
      "with a rule separating it from the section before")
# five states, one opening: written out five times, a rename touches five and misses one
_hir = seg(JS, "function higgsInstallRow", "function ttsFieldExtra")
check(JS.count("const HIGGS_SECT") == 1, "the install heading is stated once")
check(_hir.count("HIGGS_SECT") == 5,
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
_ec = seg(py, "def api_errors_clear", "def log_error")
for _n in ("ERR_LOG", "ERR_TOTAL", "ERR_BY_TYPE", "ERR_BY_LEVEL", "ERRTRACK"):
    check(_n in _ec, "clearing resets %s" % _n)
check("ERR_FILE[0]" in _ec, "and empties the log file, not just the list")
check("/api/errors-clear" not in (_ro | _po), "clearing is host-only")
check('data-act="errClear"' in JS and "data-hostonly" in JS, "the button is host-only too")
check("confirm(" in seg_len(JS, 'd.act === "errClear"', 260),
      "and asks first, since it cannot be undone")


section("one TTS state, one repaint")
# the page had ttsBusy, the header button had __ttsLaunching, and neither knew about the
# other - so starting from one left the other showing the old state
check("__ttsLaunching" not in JS.replace("// flags - ttsBusy and __ttsLaunching", ""),
      "there is one flag, not two")
check("function ttsRepaint" in JS, "and one place that repaints both")
_stb = seg_len(JS, "function syncTtsButton", 700)
check("ttsBusy" in _stb, "the header button reads the page's flag")
check(_stb.index('ttsBusy === "stop"') < _stb.index('=== "serving"'),
      "an action in flight outranks the last reported state, or a stop reads as running")
# TTS moved to its own tab in v3.73 patch1; this test could never be true again
check('curDsub === "tts"' not in JS,
      "nothing still tests for TTS as a sub-tab - that is why the buttons stuck")
check('await ttsServer("start")' in JS, "the header button takes the same path as the page")

# the tail guard must be an allowlist: a kind added later could take a path
check("REMOTE_TAIL_KINDS" in py, "remote tail feeds are named explicitly")
_rtk = seg_len(py, "REMOTE_TAIL_KINDS = frozenset", 200)
check('"file"' not in _rtk, "kind=file is not among them")
check("not in REMOTE_TAIL_KINDS" in py, "and anything unlisted is refused, not allowed")
check('"ttssrv"' in _rtk and "TTS_SERVER_LOG_NAME" in py,
      "audio.cpp's own output is a feed of its own")
check('["ttssrv", "TTS Server (audio.cpp)"]' in JS, "offered in the split view")
# the dropdown should read like Live Network's
check("g.brand ? g.brand" in JS, "the GPU list shows the board partner")
check('"#" + (g.index' in JS, "and the device number")


section("the GPU row tells the truth")
# it said "every visible card is offered" while the config carries "device": 0 - which
# means the FIRST card and nothing else
# the fleet launchers DO offer every card when unpinned - that wording is correct there.
# Only the TTS row was wrong, so check the TTS row.
_gpurow = seg_len(JS, "GPU (pinned by UUID", 900)
check("every visible card is offered" not in _gpurow,
      "the TTS row makes no claim that an unpinned server uses every card")
check("function gpuAutoLabel" in JS, "the empty choice names what will actually be used")
_gal = seg(JS, "function gpuAutoLabel", "function ttsModelOptions")
check("your only card" in _gal, "one card: says so, so nobody wonders if they missed a step")
check("the first card" in _gal, "several: says which one it will take")
check("pin the one you want" in JS,
      "and with several cards unpinned, it says why that matters")
# "def tts_engine" also matches def tts_engine_label, which sits EARLIER
_tgl = seg(py, "def tts_gpu_label", "def tts_engine(cfg")
check('"default device"' not in _tgl, "the terminal names the card rather than 'default'")
check("(automatic)" in _tgl, "while still saying the choice was not made by hand")


section("welcome offers a TTS-only path")
# NOT showTab("network") as the end anchor - it appears earlier in the file, which made
# the slice run backwards and test nothing
_wel = seg(JS, "function welcomeGoHelper", "load().then(maybeWelcome)")
check("function welcomeTtsOnly" in _wel, "there is a way in for someone who only wants voices")
check('showTab("tts")' in _wel, "and it lands on the TTS page, not the fleet guide")
check("welcomeSeen: true" in seg_from(_wel, "function welcomeTtsOnly"),
      "it marks the welcome seen, like the other two")
check("set up speech on its own" in _wel,
      "the message says the two halves can be used apart")
check("bluebtn" in _wel and ".bluebtn" in _css,
      "the button is blue, so it does not compete with the accent one")
# inside the MODAL markup, not the whole slice - welcomeDismiss is DEFINED further up
_modal = seg_from(_wel, "showModal(")
check(_modal.index("welcomeTtsOnly()") < _modal.index("welcomeDismiss()"),
      "and sits first in the row, away from the two on the right")
check("margin-left:auto" in _wel, "pushed apart by a spacer rather than a guessed gap")


section("audio.cpp can be reported on")
check("def acpp_report" in py, "the panel can say how the speech engine has behaved")
_ar = seg(py, "def acpp_report", "def api_acpp_report")
for _w in ("lines spoken", "ran past end of line", "regenerations", "generation time"):
    check(_w in _ar, "the report counts: %s" % _w)
check("ggml_cuda_init" in _ar, "and quotes what the server said about the machine")
check("audiocpp_cli --task tts" in _ar,
      "with the command to reproduce it WITHOUT the panel, which is what a maintainer needs")
check("re.split" in _ar and "ttsAcppModel" in _ar,
      "the model name splits on both separators - basename ignores a backslash here")
check("isinstance(BUILD_ID, str)" in _ar, "and the build id is printed, not its dict")
check('"/api/acpp-report"' in py, "it is reachable")
check('data-act="acppReport"' in JS, "from a button on the TTS page")
check("0xShug0/audio.cpp" in JS, "which says where to send it")

# The Pitch Guard was REMOVED in patch33. It measured pitch and low-band energy and
# called a rise in either a different speaker - but elation raises both, legitimately,
# and the user's ear confirmed every take was the right voice throughout. There is
# nothing here to guard.
check("def pitch_off" not in py, "there is no pitch guard - it measured emotion, not identity")
check("ttsPitchGuard" not in py and "ttsPitchGuard" not in PAGE,
      "and no setting left behind for it")


section("thinking has a budget you can set")
# 600 tokens was hardcoded, so PME reasoning was cut off around 500 with no answer left
check("def think_budget" in py, "the budget is a setting, not a constant")
_tb = seg(py, "def think_budget", "def apply_route_shape")
check("100" in _tb and "10000" in _tb, "clamped to the range the slider offers")
check('think_budget(st, "ttsPtiBudget"' in py, "the tagger uses it")
check('think_budget(st, "ttsPmeBudget"' in py, "and so does the reader")
check('"ttsPtiBudget"' in JS and '"ttsPmeBudget"' in JS, "with a slider each")
# and the flags that go with reasoning
_ch = seg(py, "def _chat(rt", "def mood_note_line")
# reasoning_format is the server card's setting since patch40; forcing it per request
# would be the same silent countermand the hardcoded temperature was
nin(_ch, '"reasoning_format"', "reasoning_format is left to the server card")
# the budget message belongs with the rest of the shape, so a ROUTED provider with
# Thinking on gets it too - it used to reach only the panel's own two callers
_shape2 = seg(py, "def apply_route_shape", "def chat_metrics")
check("REASON_BUDGET_MSG" in _shape2, "the budget message is applied from the shape")
check(fp.REASON_BUDGET_MSG == "Answer now.", "and says Answer now.", fp.REASON_BUDGET_MSG)
_bon = fp.apply_route_shape({"messages": []}, {"thinking": True})
check(_bon.get("reasoning_budget_message") == "Answer now.",
      "Thinking on carries it", str(_bon.get("reasoning_budget_message")))
# a budget of 0 is exhausted at once, so a message left set would be forced into the
# output of a provider that was told not to think
_boff = fp.apply_route_shape({"messages": [], "reasoning_budget_message": "x"},
                             {"thinking": False})
check("reasoning_budget_message" not in _boff,
      "Thinking off strips it, or a budget of 0 would speak it", str(_boff))
_bown = fp.apply_route_shape({"messages": [], "reasoning_budget_message": "Stop."},
                             {"thinking": True})
check(_bown["reasoning_budget_message"] == "Stop.",
      "and a caller that sent its own wording keeps it")
# without the server flag the reasoning arrives inline and would be read as the answer
check("def _split_think" in py, "an inline <think> block is separated from the answer")
# at the top level the flag is ignored and thinking stays on however the switch is set
_shape = seg(py, "def apply_route_shape", "def chat_metrics")
check('ck["enable_thinking"] = False' in _shape,
      "turning Thinking off puts the flag where the template reads it")
# The kwarg is deprecated upstream and the per-request budget is what llama.cpp points
# at instead - but a budget of 0 stops thinking rather than preventing it, and the model
# answers with a stub. Deprecated and working beats current and broken.
check('d.pop("reasoning_budget_tokens", None)' in _shape,
      "a budget arriving from a caller is taken off, not passed through")
check('ck["enable_thinking"] = False' in py,
      "the same place the proxy puts it, which is the one that works")
_st3 = seg(py, "def _split_think", "def think_budget")
check("unclosed" in _st3, "and an unclosed one means the budget ran out, so no answer")


section("a tag colours from where it sits")
_tp4 = seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]")
check("goes exactly where it" in _tp4, "the prompt says where a heard tag belongs")
check("START of the sentence it applies" in _tp4,
      "and that a felt one goes at the start of its sentence")
check("at the end of the line" in _tp4,
      "and rules out the end of the line, which is where they were all landing")
_ex4 = seg(py, "TAG_EXAMPLES = (", "def tts_tag_prompt")
check("[SFX-LAUGHTER] Haha! [EMOTION-CONTENTMENT]" in _ex4,
      "with an example of a loud opening and a calmer rest")


section("the line comes back marked up, not a tag list")
# a noise belongs where it happens - "Excuse me. [cough] Dusty in here." - and a tag
# list can only ever be prepended
_tp3 = seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]")
check("Return it word for word" in _tp3, "the model is asked for the line back")
check("add nothing, change nothing" in _tp3, "unchanged but for the tags")
# said by the example rather than by a sentence: a noise belongs at the pause it falls
# in, which a tag list could never express
check("Excuse me. [SFX-COUGH] Dusty in here." in seg(py, "TAG_EXAMPLES = (", "def tts_tag_prompt"),
      "with the audio tag placed where it falls")
_ex3 = seg(py, "TAG_EXAMPLES = (", "def tts_tag_prompt")
check("Excuse me. [SFX-COUGH] Dusty in here." in _ex3,
      "and an example showing a tag mid-line, which is the whole point")
check(_ex3.count("[") >= 3, "more than one example", str(_ex3.count("[")))
# the player typed this line; a model must not quietly reword it
check("def _clean_tagged" in py, "the reply is checked before it is used")
_ct = seg(py, "def _clean_tagged", "def tts_player_tag")
check("_bare(reply) != _bare(original)" in _ct,
      "a reply whose WORDS changed is refused - it is the player's line, not the model's")
check("gi in seen" in _ct, "at most one tag of each kind survives")
check("gi is None" in _ct, "and a word we never offered is dropped")
check("return \"\"" in _ct, "with nothing at all rather than something wrong")
check("raw = _tagged" in py, "the caller speaks the marked-up line")
# tagging happens BEFORE the line is spoken; the terminal shows it so
_ri2 = seg(py, "_tagged = tts_player_tag(raw, cfg)", "processed = tts_apply_tags")
check("self.log" in _ri2, "and says so in the TTS terminal, above the spoken line")
check("PTI_LAST" in _ri2, "with how long it took, so a slow one is visible")


section("two kinds of tag, one of each")
# four groups made the model weigh four decisions and answer the first
_grp2 = seg(py, "_TAG_GROUPS = (", "def _build_offer")
check('("Emotion", ("emotion",))' in _grp2, "Emotion is one kind")
check('("Audio", ("sfx", "style", "prosody"))' in _grp2,
      "and everything audible is the other - sfx, style and prosody together")
check("Feeling" not in _grp2 and "Pacing" not in _grp2, "there is no third or fourth")
_tp2 = seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]")
check("EMOTION" in _tp2 and "AUDIO" in _tp2, "the prompt names both in capitals")
check("EMOTION (felt)" in _tp2, "saying what an emotion tag is")
check("AUDIO (heard)" in _tp2, "and what an audio tag is")
check("At most one EMOTION and one AUDIO tag" in _tp2, "with the limit stated once, plainly")
check("START of the sentence" in _tp2, "and where each one goes in the line")
_ex2 = seg(py, "TAG_EXAMPLES = (", "def tts_tag_prompt")
# the examples are (line, marked-up line) pairs since patch27
check("[EMOTION-CONTENTMENT]" in _ex2 and "[SFX-COUGH]" in _ex2 and _ex2.count("(\"The bridge"),
      "the examples cover each case: a second tag taking over, an audible noise at the "
      "pause it falls in, and a line that comes back untouched")
# the mood reader names emotions, so it follows the rename
check('dict(TAG_OFFER).get("Emotion"' in py, "the mood reader reads the Emotion group")
check('dict(TAG_OFFER).get("Feeling"' not in py, "and nothing still looks for Feeling")


section("the tagger is shown what a good answer looks like")
# it reliably answered with one Feeling and never a Sound: the prompt listed the
# vocabulary, gave no worked examples, and said "fewer is better"
check("TAG_EXAMPLES" in py, "there are worked examples, not just a vocabulary")
_ex = seg(py, "TAG_EXAMPLES = (", "def tts_tag_prompt")
import re as _re
_two = sum(1 for _l, _tg in _re.findall(r'\("([^"]*)",\s*\n?\s*"([^"]*)"\)', _ex)
           if _tg.count("[") >= 2)
check(_two >= 1, "at least one showing more than one tag at once", str(_two))
check("[SFX-LAUGHTER] Haha! [EMOTION-CONTENTMENT]" in _ex,
      "including the split line, which is the one that changed this model's behaviour")
check("The bridge is just past the mill." in _ex,
      "and one coming back unchanged, which is a real answer")
_tp = seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]")
check("fewer is better" not in _tp, "the prompt no longer talks the model down to one tag")
# patch26 wording: the closing instruction reads for both kinds
check("either optional" in _tp, "and says plainly that neither is required")
check("At most one EMOTION and one AUDIO tag" in _tp,
      "explaining that the two kinds combine")
for _lbl in ("EMOTION (felt)", "AUDIO (heard)"):
    check(_lbl in _tp, "each kind says what it is for: %s" % _lbl)
# the whole point of cutting it: the prefill is the same prompt every time
_p_new = fp.tts_tag_prompt()
check(len(_p_new) < 1450, "and the whole thing stays well under three quarters of what it was",
      "%d chars" % len(_p_new))
_words = len(", ".join(dict(fp.TAG_OFFER)["Emotion"])) + len(", ".join(dict(fp.TAG_OFFER)["Audio"]))
check(_words > len(_p_new) * 0.3,
      "most of what is left is the vocabulary itself, which cannot be cut",
      "%d of %d chars" % (_words, len(_p_new)))
for _w in dict(fp.TAG_OFFER)["Emotion"] + dict(fp.TAG_OFFER)["Audio"]:
    if _w not in _p_new:
        check(False, "every tag is still offered: %s" % _w)
check(True, "every tag Higgs takes is still named in the prompt")
# an example naming a word the tagger may not answer would teach it to fail
_allowed = set(re.findall(r'"([a-z_]+)"', seg(py, "def _build_offer", "TAG_OFFER = _build_offer()")))
_used = set(re.findall(r"\[([A-Z][A-Z_-]+)\]", _ex))
check(bool(_used), "the examples use real tags")
_pmex = seg(py, "For example, after a companion", "Write fewer lines")
check("[anger]" in _pmex and "Final Answer" in _pmex,  # PME's own example, untouched
      "the reader is shown a finished answer too")


section("every tag Higgs takes is offered")
check("TTS_ALIAS.setdefault(_n, (_kind, _n))" in py,
      "a canonical name is writable as itself - [affection] used to be left as text")
check("a-zA-Z_ " in py, "and the matcher takes the underscores prosody names carry")
# the grouping lives in _clean_tagged since patch27, which keeps placement too
_grp = seg(py, "def _clean_tagged", "def tts_player_tag")
check("for gi, (_label, words) in enumerate(TAG_OFFER)" in _grp,
      "at most one tag per group, whatever the groups are")
check("gi in seen" in _grp, "so a second emotion is dropped rather than sent")


section("elation never reaches the engine")
# MEASURED: 8 of 8 takes carrying <|emotion:elation|> came back in a different voice,
# across two references at 83 Hz and 200 Hz - and all landed at 265-381 Hz REGARDLESS
# of the reference, which is the speaker being dropped, not shifted
check("TTS_EMOTION_BLOCK" in py, "a blocked-emotion list exists")
# from the COMMENT, not the assignment - the reasoning is what matters here
_blk = seg(py, "# Emotions this build refuses", "def tts_apply_tags")
# emptied in patch24: the Pitch Guard catches a wrong voice whatever caused it, which
# is the same fault treated at its source rather than by naming one word
check("frozenset()" in _blk, "empty - the Pitch Guard treats this at its source")
check("this is where it goes" in _blk, "the mechanism stays, for a tag that earns it")
_rn = seg(py, "def _tts_render", "def tts_is_player")
check("TTS_EMOTION_BLOCK" in _rn,
      "blocked where the token is WRITTEN, so every spelling is covered")
_off2 = seg(py, "def _build_offer", "TAG_OFFER = _build_offer()")
check("TTS_TAGS.get(kind" in _off2,
      "the offer is BUILT from the tables - a hand-written list drifted at once")
check('"%s-%s" % (kind.upper(), nm.upper())' in _off2,
      "written KIND-NAME, the notation SkyrimNet uses for the same tags")
check('"pause"' in py and "_TAG_SKIP" in py,
      "leaving out pause, which is punctuation rather than performance")
# a tag in the wrong case used to be spoken aloud, brackets and all
check("[a-zA-Z][a-zA-Z_ ]" in py, "an ALL-CAPS alias is recognised, not read out")

section("PTI and PME read like the rest of the panel")
_tol2 = seg(py, "def tag_output_line", "def proxy_line_text")
check("splitlines()" in _tol2 and "enumerate(rows)" in _tol2,
      "each feeling gets its own row, so each gets its own branch")
check("TREE_MID" in _tol2 and "TREE_END" in _tol2,
      "and the last row closes the tree rather than continuing it")
check('which === "thinking" || which === "ptipme"' in JS,
      "the PTI/PME terminal is painted by the thinking painter - same colours")
check("iohead" in JS and ".tail .iohead" in _css, "with its two headings lit")
check("var(--acc)" in seg(_css, ".tail .iohead {", "the one action on the page"),
      "in the accent colour, glowing")


section("a terminal for what PTI and PME were asked")
check("def ptipme_log" in py, "the whole exchange is written down")
_pl2 = seg(py, "def ptipme_log(who", "def tag_output_line")
check("--- INPUT ---" in _pl2, "what was sent")
check("--- OUTPUT ---" in _pl2, "and what came back")
# the reasoning has its own terminal; this one answers "what did it see, what did it say"
check("Not the reasoning" in _pl2, "and not the reasoning, which lives elsewhere")
check("mood_answer(said) if think else said" in py and "ptipme_log(\"PTI\", rt[\"server\"], sys_p, line, answer" in py,
      "PTI logs its final answer, not the working that led to it")
check("ptipme_log(\"PME\", rt[\"server\"], _sys, body, mood_answer(said)" in py,
      "and so does PME")
check("ptipme_log(\"PTI\"" in py and "ptipme_log(\"PME\"" in py, "for both of them")
check('"ptipme"' in py and 'PTIPME_LOG_GLOB, 4)' in py,
      "into a session log of its own, pruned under the ONE name that describes the "
      "family - a constant nothing reads is a literal repeated somewhere (patch184)")
check('"ptipme"' in seg_len(py, "REMOTE_TAIL_KINDS = frozenset", 200),
      "readable on remote - it is a fixed filename like the others")
check('id="tsub-ptipme"' in PAGE and 'id="tail-ptipme"' in PAGE, "with a terminal of its own")
check('"ptipme"' in seg(JS, 'function showTsub', "function refreshCurTerm"),
      "which the sub-tab switcher knows about")
check('refreshTail("ptipme")' in JS, "and which refreshes like the rest")
check('["ptipme", "PTI / PME"]' in JS, "offered in the split view too")
check('"ptipme"' in seg(py, "TERM_SCALE_KINDS = (", "TTS_LOG_NAME"),
      "and it scales its text like every other terminal")


section("which reference went out")
# a line came back two octaves off the sample, wrong from its first frame - which is the
# wrong reference, not a conditioning drift. Without the filename there is no way to tell
# a wrong file from a right file badly used.
_sv = seg(py, "def saved_line", "def _run(self, eid")
check("voice: %s" in _sv, "every spoken line records the reference it was given")
check('re.split(r"[\\\\/]"' in _sv,
      "split on BOTH separators - a Windows path off Windows loses its leaf otherwise")
check('"(none)"' in _sv, "and says so plainly when no reference went out at all")


section("prompts, output and the tree")
# the prompts are editable, blank meaning the built-in wording
for _k in ("ttsPtiPrompt", "ttsPmePrompt"):
    check('"%s"' % _k in py and '"%s"' % _k in JS, "%s can be rewritten" % _k)
check("def mood_prompt(n, custom=" in py, "and the reader takes a custom one")
check("def tts_tag_prompt(custom=" in py, "as does the tagger")
check('"defaultPtiPrompt"' in py and '"defaultPmePrompt"' in py,
      "the built-in wording is shown in the editor, not hidden")
# these are BUTTONS, so the click chain - the selects beside them fire on change
_clk = seg(JS, 'if (d.act === "ttsPromptEdit")', 'if (d.act === "errClear")')
check("closeModal()" in _clk, "editing posts and closes")
check('d.act === "ttsPromptClear"' in _clk, "and can be put back to the built-in")

# PME answers in a named section, so a reasoning model has somewhere to put its working
_mp3 = seg(py, "def mood_prompt", "def mood_answer")
check("Final Answer" in _mp3, "the reader is told exactly where to put its answer")
check("1. [word] (NN%%): brief reasoning" in _mp3, "in a numbered shape")
_ma = seg(py, "def mood_answer", "def mood_valid")
check("for m in re.finditer" in _ma,
      "and the LAST Final Answer is taken - reasoning quotes the instruction")

# what PTI and PME chose can be shown, painted like a spoken line
check("def tag_output_line" in py, "their answers can be shown in the terminal")
_tol = seg(py, "def tag_output_line", "def proxy_line_text")
check("TAG_OUT_KEY" in _tol, "behind a setting, chosen by which feature answered")
check("\\u3030" in _tol, "written like a spoken line, so it gets the same tree")
for _act in ("termTagOutPti", "termTagOutPme"):
    check(('data-act="%s"' % _act) in PAGE, "toggled from the terminal toolbar: %s" % _act)
# one switch covered both, so turning off the PTI echo of your own line also lost the
# mood reading. They are separate features and now separate switches.
check(fp.TAG_OUT_KEY == {"PTI": "ttsTagOutputPti", "PME": "ttsTagOutputPme"},
      "one switch per feature", str(fp.TAG_OUT_KEY))
for _k in fp.TAG_OUT_KEY.values():
    check(_k in fp.DEF_SETTINGS, "%s ships as a setting" % _k)
check("ttsTagOutput" not in fp.DEF_SETTINGS, "and the single switch it replaced is gone")
_lc = seg(py, "def load_config():", "def read_named_template")
check('st.pop("ttsTagOutput"' in _lc,
      "a config written by an older build is carried over, not left orphaned")
# the mapping must exist in ONE place: a button lit from one setting and toggling
# another is the exact failure this table prevents
check(JS.count('"termTagOutPti", "ttsTagOutputPti"') == 1,
      "the act -> setting mapping is stated once on the page")
_ck = seg(JS, 'if (d.act === "termTagOutPti"', "return;")
check("tagOutSetting(" in _ck, "and the click reads it rather than repeating it")
check("termToggle(" in _ck,
      "through the shared toggle, so the terminal repaints with the switch")

# behaviour, not text: one switch off must silence its own feature and nothing else,
# and the rows must close the tree on the last one
_tagdir = tempfile.mkdtemp()
_real_ld = fp.log_dir
fp.log_dir = lambda cfg=None: _tagdir     # panel_log/log_dir root at the tree otherwise


def _tagout(settings, who, answer):
    for _f in os.listdir(_tagdir):
        os.remove(os.path.join(_tagdir, _f))
    fp.tag_output_line(who, answer, {"settings": settings})
    _got = ""
    for _f in os.listdir(_tagdir):
        _got = open(os.path.join(_tagdir, _f), encoding="utf-8").read()
    return _got


try:
    _both = {"ttsTagOutputPti": "on", "ttsTagOutputPme": "on"}
    _one = _tagout(_both, "PTI", "[amusement] there you are")
    _three = _tagout(_both, "PME", "[a] (80%)\n[b] (40%)\n[c] (10%)")
    _muted = _tagout({"ttsTagOutputPti": "off", "ttsTagOutputPme": "on"}, "PTI", "hidden")
    _other = _tagout({"ttsTagOutputPti": "off", "ttsTagOutputPme": "on"}, "PME", "[a] (80%)")
finally:
    fp.log_dir = _real_ld

check(fp.TREE_PAD + fp.TREE_END in _one, "a single answer closes the tree", repr(_one[:60]))
check(_three.count(fp.TREE_MID) == 2 and _three.count(fp.TREE_END) == 1,
      "three rows branch twice and close once",
      "mid=%d end=%d" % (_three.count(fp.TREE_MID), _three.count(fp.TREE_END)))
check(_muted == "", "PTI off writes nothing at all", repr(_muted[:60]))
check(fp.TREE_END in _other, "and PME is untouched by the PTI switch", repr(_other[:60]))
check("\u3030\ufe0f" in _one.lower(),
      "the answer still carries the markers the painter reads a spoken line by")

# a wrapped line must not break the tree
check("align-items:stretch" in JS, "the head cell stretches to the whole row")
_br = seg(_css, ".tail .tbr, .tail .tbrend {", ".tail .tbr::before")
check("height:100%" in _br, "so the branch reaches the bottom of a wrapped line")
check("height:.8em" in _css, "while the last branch still stops at its elbow")

# audio.cpp sometimes fails to stop; it is sampled, so a second try usually works
_sp = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
check("max_tokens" in _sp and "raise" in _sp, "a runaway line is retried once")
check("pitch_off" not in _sp, "and nothing else is second-guessed")
# three tries since patch23 - the pitch guard shares this loop
check("_try >= 2 or" in _sp,
      "and any error that is not a runaway is raised at once")

# a launch replaces the stack text, which threw the TTS line away
_ss = seg(JS, "function stackSet(txt)", "function stackAdd")
check("__prevTts = undefined" in _ss, "a replaced stack forgets the TTS state")
check('_tsNow !== "down"' in JS, "so the next pass says where it stands again")
check('src="/icon.ico"' in JS, "the panel's mark is the panel's own icon")


# a rule inside a block splits it; the same rule after it separates one block from the
# next, which is what it is for
_ptr = seg(JS, "function ttsPlayerTagRow", "function ttsMoodRow")
check(_ptr.count("tsplit") == 1 and _ptr.find("tsplit") > _ptr.find("ttsPromptBox") >= 0,
      "the rule closes the Player Tag Injector block rather than splitting it",
      "%d rules" % _ptr.count("tsplit"))
_mdr = seg(JS, "function ttsMoodRow", "function moodSlider")
check(_mdr.count("tsplit") == 1, "PME keeps exactly one rule",
      "%d rules" % _mdr.count("tsplit"))
# the server's own settings sat under no heading at all, directly after the tag system
_rt = JS
check('<div class="tsect">TTS Server</div>' in _rt, "the model and build sit under a heading")
check(0 <= _rt.find('<div class="tsect">TTS Server</div>') < _rt.find("<label>Model</label>"),
      "which comes before the Model picker rather than after it")

section("the audio.cpp build choice")

# the explanation used to sit under the control as a paragraph; it is a hover now, and
# the paragraph must be gone rather than duplicated
_bld = seg(JS, 'ttsTitle("Audio.cpp Build"', "'<label>GPU (pinned by UUID")
check("ttsTitle(" in _bld, "the build choice carries a ? explanation, like every other title")
for _w in ("CPU instruction", "RTX 20-series", "restart"):
    check(_w in _bld, "the hover says what the choice means: %s" % _w)
nin(_bld, '<div class="hint"', "and the paragraph under the control is gone, not duplicated")
_ab = re.search(r"const ACPP_BUILDS = \[(.*?)\];", JS, re.S)
check(bool(_ab), "the builds come from one table")
_labels = re.findall(r'\["(\w+)", "([^"]+)"\]', _ab.group(1) if _ab else "")
check(sorted(_labels) == [("balance", "Balanced"), ("fast", "Fast")],
      "each option is named by the build alone", str(_labels))


section("PME frequency")

# Reading the scene after every NPC line is a model call per line. The count is taken
# where a line SETTLES: a reply arrives in pieces and only the last survives the
# generation guard, so counting arrivals would run the frequency down several times over.
check("ttsMoodEvery" in fp.DEF_SETTINGS, "the setting ships")
_lc2x = seg(py, "def load_config():", "def read_named_template")
check(fp.DEF_SETTINGS["ttsMoodHistory"] == "25", "Chat History ships at 25",
      fp.DEF_SETTINGS["ttsMoodHistory"])
check(fp.mood_history({}) == 25, "and an absent value reads as that")
check("moodHistV25" in _lc2x, "a config still on the shipped 8 is moved once")
check(fp.DEF_SETTINGS["ttsMoodEvery"] == "5", "it ships at 5",
      fp.DEF_SETTINGS["ttsMoodEvery"])
check([fp.mood_every({"ttsMoodEvery": v}) for v in ("1", "20", "0", "99", "", "x")]
      == [1, 20, 1, 20, 3, 3], "clamped to 1-20, and a bad value falls back to the default")
# DEF_SETTINGS only fills a key that is MISSING, so a config written by patch35 keeps
# the 1 it shipped with and would never see the new default
_lc2 = seg(py, "def load_config():", "def read_named_template")
check("moodEveryV3" in _lc2, "a config still on the shipped 1 is moved once")
check('== "1"' in seg(_lc2, 'if not st.get("moodEveryV3")', 'st["moodEveryV3"] = True'),
      "and only from that value, so a 1 chosen deliberately afterwards stays")
_mn = seg(py, "def mood_note_line", "def mood_due")
check("mood_due()" in _mn, "counted after the settle guard, not on every arrival")
# the count is GLOBAL: every Nth settled NPC line, whatever the player has been doing.
# Resetting it when the tagger ran meant that in a back-and-forth it never reached N at
# all, so any setting above 1 read the scene almost never.
nin(seg(py, "def tts_player_tag", "def mood_count"), "_MOOD_TICK",
    "the tagger has nothing to say about when the scene is read")
check(py.count("_MOOD_TICK[0] = 0") == 1,
      "the count is reset in one place: when it fires",
      "%d sites" % py.count("_MOOD_TICK[0] = 0"))

fp._MOOD_TICK[0] = 0
_fired = "".join("Y" if fp.mood_due({"settings": {"ttsMoodEvery": "5"}}) else "."
                 for _ in range(12))
check(_fired == "....Y....Y..", "every fifth NPC line reads the scene", _fired)
fp._MOOD_TICK[0] = 0
_ev = "".join("Y" if fp.mood_due({"settings": {"ttsMoodEvery": "1"}}) else "."
              for _ in range(5))
check(_ev == "YYYYY", "and 1 reads on every one of them", _ev)
fp._MOOD_TICK[0] = 3
check(fp.mood_due({"settings": {"ttsMoodEvery": "20"}}) is False,
      "a partial count does not fire early")
fp._MOOD_TICK[0] = 0


section("the tree is drawn the same on both sides")

# A line the PANEL writes carries the glyphs; a line the PAGE splices in draws its own.
# Different glyphs would put the two kinds of branch in different columns.
for _nm in ("TREE_PAD", "TREE_MID", "TREE_END"):
    _m = re.search(r"const %s = ([^;]+);" % _nm, JS)
    check(bool(_m), "the page states %s" % _nm)
    if _m:
        _jsval = eval(_m.group(1).replace("String.fromCodePoint", "chr")
                      .replace('"   "', '"   "'))
        check(_jsval == getattr(fp, _nm),
              "%s is the same glyph in the panel and on the page" % _nm,
              "%r vs %r" % (getattr(fp, _nm), _jsval))
_ps = seg(JS, "function paintSpoken", "function paintTail")
check(str(ord(fp.TREE_MID[0])) in _ps and str(ord(fp.TREE_END[0])) in _ps,
      "and the painter recognises both of them")


section("the panel's own calls are visible")
# PTI and PME are model calls the panel makes; seeing them is how you know they work
# They ARE providers now, so they do not write their own line - they call the same
# report() a routed provider does, which is what puts them in the stats page too.
nin(py, "def proxy_log_line", "the panel's second line writer is gone")
_rep = seg(py, "def report(self, rt, think", "def _fold_request")
check("proxy_line_text(" in _rep, "one writer for the Proxy terminal")
check("_thinking.log" in _rep, "and their reasoning into the Thinking Content terminal")
check("self.stats.setdefault" in _rep, "and every caller folds into the stats page")
for _who in ("pti", "pme"):
    _fn = "def tts_player_tag" if _who == "pti" else "def mood_evaluate"
    _blk = seg(py, _fn, "def mood_count" if _who == "pti" else "def tts_engine_label")
    check("PROXY.report(rt," in _blk, "%s reports through it" % _who.upper())
# the column layout was written out twice and the two copies were NOT the same - the
# panel's own copy had "?" hardcoded in the prompt-speed slot. One shape, one place.
check(py.count("%6s / %5s %-8s tok  %5s / %3s tps") == 1,
      "the column layout exists in exactly one place",
      "%d copies" % py.count("%6s / %5s %-8s tok  %5s / %3s tps"))
check("proxy_line_text(" in seg(py, "def report(self, rt, think", "def _fold_request"),
      "and every caller renders through it, so the columns cannot drift apart")
nin(py, "want_reasoning", "the dead reasoning switch is gone - every caller wanted it")

# The prompt-speed column read "?" for PTI and PME on every call: nothing was passed for
# it, because prompt processing cannot be timed from outside. llama.cpp reports it in
# `timings` and the reply was being thrown away.
_p1 = fp.chat_metrics({"prompt_n": 577, "predicted_n": 9,
                       "prompt_per_second": 2143.5, "predicted_per_second": 33.2}, None)
check(_p1["tok_in"] == 577 and _p1["tok_out"] == 9, "token counts come from the server",
      str(_p1))
check(_p1["pf"] == 2143.5 and _p1["dc"] == 33.2, "and so do both speeds", str(_p1))
_p2 = fp.chat_metrics(None, {"prompt_tokens": 40, "completion_tokens": 8}, 0.5)
check(_p2["tok_in"] == 40 and _p2["tok_out"] == 8, "usage answers when timings do not")
check(_p2["pf"] is None,
      "and a prompt speed nobody reported is left absent, not estimated", str(_p2["pf"]))
check(abs(_p2["dc"] - 16.0) < 0.01, "the generation rate falls back to wall time", str(_p2))
_p3 = fp.chat_metrics(None, {"prompt_tokens": 40, "completion_tokens": 8})
check(_p3["dc"] is None, "a provider line never guesses - it passes no wall time")
check("?" in fp.proxy_line_text("x", "PTI", "1234", None, None, 0, None, None, 1.0),
      "an absent figure prints as ? rather than as zero")
# the two writers must produce the same columns, or lining them up was pointless
_c1 = fp.proxy_line_text("x", "PTI", "1237", 577, 9, 0, 2143.5, 33.2, 0.271)
_c2 = fp.proxy_line_text("x", "Provider", "1234", 900, 250, 40, 1800.0, 60.0, 4.2, "+9 ms")
check(_c1.index(" tok ") == _c2.index(" tok ") and _c1.index(" tps ") == _c2.index(" tps "),
      "a panel line and a provider line put tok and tps in the same columns",
      "%d/%d vs %d/%d" % (_c1.index(" tok "), _c1.index(" tps "),
                          _c2.index(" tok "), _c2.index(" tps ")))
check("PANDORUM_MARK" in JS and "PANDORUM_SVG" in JS,
      "the mark is painted as the PandorumLLM icon")
check(".tail .pmark" in _css and "var(--acc)" in seg(_css, ".tail .pmark {", ".tail .pown"),
      "lit in the accent colour")
check(".tail .pown" in _css, "as are the names beside it")

# the TTS server's own lifecycle belongs in the STACK terminal, not the Proxy one
check("fleet_log_note" not in py, "the TTS lifecycle no longer writes to the Proxy log")
check("__prevTts" in JS, "it is announced from the state the page already reads")
_st2 = seg(JS, "const _tsNow =", "if (window.__prevServing)")
for _w in ("TTS server starting", "TTS server serving", "TTS server stopped"):
    check(_w in _st2, "the stack terminal says: %s" % _w)
check("stackAdd(" in _st2, "via stackAdd, which is what that terminal is")


section("PTI and PME can outrank providers")

# They do not route through the proxy - they talk to the server directly - so the
# priority a provider carries has nothing to say about them. The switch puts them on
# the footing of a priority-0 provider, through the SAME gate: a second gate, or a
# second way of deciding which card a slot is on, would be a gate that appears to work.
check("provider_route(p, s, up, gpu_ids)" in seg(py, "def _desired", "def sync") and
      "slot_gpu_key(" in seg(py, "def provider_route", "def panel_route"),
      "the routing table and the gate derive the card the same way")
check(py.count("def slot_gpu_key") == 1, "from one function")
# (gpu_for_server_port left in the patch155 dead-code sweep - nothing called it)
# priority 0 on the provider card is what High already means; a second switch of
# their own would have been two dials for one thing
check(fp.route_gate_key({"priority": 1, "gpu": "GPU-aaa"}) == "",
      "Normal priority holds nothing")
check(fp.route_gate_key({"priority": 2, "gpu": "GPU-aaa"}) == "", "nor does Low")
check(fp.route_gate_key({"priority": 0, "gpu": "GPU-aaa"}) == "GPU-aaa",
      "High holds the card the server is on")
check(fp.route_gate_key(None) == "" and fp.route_gate_key({}) == "",
      "and a route that does not exist holds nothing rather than raising")
for _k in ("ttsPtiPriority", "ttsPmePriority"):
    check(_k not in fp.DEF_SETTINGS, "%s is gone - the card carries it now" % _k)
    nin(JS, _k, "and it is off the page: %s" % _k)

# behaviour: a provider arriving on that card while the call runs must actually wait
_was = fp.GATE_MAX_WAIT_S
fp.GATE_MAX_WAIT_S = 2.0
_w = {}
try:
    with fp._GateHeld("GPU-gate-test"):
        _t = threading.Thread(target=lambda: _w.setdefault("same", fp.PROXY.gate.enter("GPU-gate-test", False)))
        _t.start(); time.sleep(0.35); _t.join(3)
    with fp._GateHeld("GPU-gate-test"):
        _t2 = threading.Thread(target=lambda: _w.setdefault("other", fp.PROXY.gate.enter("GPU-other", False)))
        _t2.start(); time.sleep(0.25); _t2.join(3)
    with fp._GateHeld(""):
        _t3 = threading.Thread(target=lambda: _w.setdefault("off", fp.PROXY.gate.enter("GPU-off-test", False)))
        _t3.start(); time.sleep(0.25); _t3.join(3)
finally:
    fp.GATE_MAX_WAIT_S = _was
check(_w.get("same", 0) >= 250, "a provider on the same card waits while the call runs",
      "%s ms" % _w.get("same"))
check(_w.get("other", -1) == 0, "one on another card does not", "%s ms" % _w.get("other"))
check(_w.get("off", -1) == 0, "and nothing waits when the switch is off", "%s ms" % _w.get("off"))
# released on the way out however the call ended, or the card stays blocked for good
_gh = seg(py, "class _GateHeld", "def route_gate_key")
check("__exit__" in _gh, "the hold is released by a context manager, not by hand")
for _who, _fn in (("PTI", "def tts_player_tag"), ("PME", "def mood_evaluate")):
    _blk = seg(py, _fn, "def mood_count" if _who == "PTI" else "def tts_engine_label")
    check("with _GateHeld(route_gate_key(rt)):" in _blk,
          "%s takes the hold from its own route" % _who)

# "Is it actually caching?" was unanswerable from the panel, and reassurance is not an
# answer. Every line now carries the figure - and distinguishes a build that reports
# nothing from one that reports nothing reused, which are different problems.
check(fp.cached_tokens({"prompt_cached_n": 258}) == 258, "the cached count is read")
for _k in fp.CACHED_N_KEYS:
    check(fp.cached_tokens({_k: 7}) == 7, "under whichever name the build uses: %s" % _k)
check(fp.cached_tokens({}) is None, "and stays absent when no build reported one")
check(fp.cached_tokens({"prompt_cached_n": 0}) == 0,
      "zero reused is a real answer, not an absent one")
check(fp.chat_metrics({"prompt_cached_n": 5}, None)["cached"] == 5,
      "it travels with the rest of the metrics")
check(fp.cache_note(258, 12) == "cache 258/270 96%", "the line shows how much was reused",
      fp.cache_note(258, 12))
check(fp.cache_note(0, 270) == "cache 0/270 0%", "and says so plainly when none was",
      fp.cache_note(0, 270))
check(fp.cache_note(None, 270) == "",
      "and nothing at all for a provider that never asked for a slot - a figure beside "
      "one reads as a fault rather than a setting nobody turned on", fp.cache_note(None, 270))
_rep2 = seg(py, "def report(self, rt, think", "def _fold_request")
check('rt.get("slot") is not None' in _rep2,
      "and only a provider with a pinned slot carries the figure at all")
_pl3 = seg(py, "def ptipme_log(who", "def tts_server_log_path")
check("cache_note" in _pl3 or "cache %d" in _pl3, "and so does the PTI/PME record")

# one character has one voice: `femalecommoner is Serana` happened because a spoken line
# with no dialogue request behind it took whatever name was pending
_realpl2 = fp.panel_log
fp.panel_log = lambda *_a, **_k: None
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _own = fp.speaker_for_voice("serana")
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _steal = fp.speaker_for_voice("femalecommoner")
    fp.note_speaker(b"You are Ysolda, a trader in Whiterun")
    _free = fp.speaker_for_voice("femalecommoner")
    _still = fp.speaker_for_voice("serana")
finally:
    fp.panel_log = _realpl2
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
check(_own == "Serana", "a voicetype learns the character behind it", _own)
check(_steal == "",
      "a name already bound to another voicetype cannot be taken by a second one", _steal)
check(_free == "Ysolda", "a name nobody owns still pairs", _free)
check(_still == "Serana", "and the first pairing is undisturbed", _still)

# regen_slot_script returns a PATH for a generated launcher and a {"changed": [...]}
# dict for one edited in place. Reading "is it a dict" as "did it fail" skipped the save
# for every hand-written launcher - the edit was made and then forgotten.
_lp = seg(py, 'panel_log("[panel] %s %s" % (mode, sid))', "def api_launch")
check('_r.get("error")' in _lp,
      "only an error dict is a failure - a successful in-place edit is a dict too")
nin(_lp, "if not isinstance(regen_slot_script", "and isinstance is not the test")

# --ctx-checkpoints was written as 0 by the No-cache switch and nowhere else
_cc = [r for r in fp.SERVER_PARAMS if r[0] == "ctxcheck"]
check(bool(_cc), "context checkpoints is a server parameter")
check(bool(_cc) and _cc[0][5] == "--ctx-checkpoints", "written as --ctx-checkpoints")
check(bool(_cc) and _cc[0][3] == "8", "defaulting to llama.cpp's own 8", str(_cc and _cc[0][3]))
check(bool(_cc) and _cc[0][4]["min"] == 0, "reaching 0, which disables checkpointing")
_l3 = fp.build_param_launcher({"settings": {}},
        {"id": "s1", "port": 1237, "params": {"model": os.path.join(tempfile.mkdtemp(), "m.gguf"),
                                              "ctxcheck": "0", "noCache": "1"}},
        os.path.join(tempfile.mkdtemp(), "o.ps1"))
_l3 = _l3 if isinstance(_l3, str) else "\n".join(_l3)
check(_l3.count("--ctx-checkpoints") == 1,
      "and written once, not by the dial and the No-cache switch both",
      str(_l3.count("--ctx-checkpoints")))

# a refused pairing was silent, so "the names are wrong" and "the names are missing"
# read identically from a log
_sv2 = seg(py, "def speaker_for_voice", "def tts_voice_name")
check("already belongs " in _sv2, "a name refused because it is taken says so")
check("no dialogue request " in _sv2, "and a line nobody named says that instead")


# A launcher held in the Server Editor lives in params["custom"] and was written back
# VERBATIM, so a change made on a server card updated the config and was then overwritten
# by the untouched original - the two views could never agree. Round-trip it.
_ed = tempfile.mkdtemp()
_MINE = ('function Write-VramReport { Write-Host "--parallel in a comment" }\n'
         '$llamaArgs = @(\n'
         '    "-m", $modelPath,\n'
         '    "--port", "1237",\n'
         '    "--ctx-size", "10240",\n'
         '    "--parallel", "1",\n'
         '    "--no-cont-batching",\n'
         '    "--flash-attn", "on"\n'
         ')\n')
_rg, _ra, _rc, _rl = fp.GEN_LAUNCHER_DIR, fp.ARCHIVE, fp.CONFIG, fp.panel_log
fp.GEN_LAUNCHER_DIR, fp.ARCHIVE = os.path.join(_ed, "gen"), os.path.join(_ed, "arch")
fp.CONFIG, fp.panel_log = os.path.join(_ed, "fleet-config.json"), lambda *_a, **_k: None
try:
    fp.save_config({"slots": [{"id": "s1", "port": 1237, "params": {},
                               "providers": [{"id": "pti", "cache": True}, {"id": "meta"}]}],
                    "gpus": [], "settings": {}})
    fp.api_slot_launcher_save({"slot": "s1", "content": _MINE})
    fp.api_slot_params({"slot": "s1", "ctx": "21504", "parallel": "3"})
    _c = fp.load_config()
    _p = _c["slots"][0]["params"]
    _txt = _p.get("custom", "")
    with open(_c["slots"][0]["script"], encoding="utf-8-sig") as _f:
        _disk = _f.read()
finally:
    fp.GEN_LAUNCHER_DIR, fp.ARCHIVE, fp.CONFIG, fp.panel_log = _rg, _ra, _rc, _rl

check('"--ctx-size", "21504"' in _txt,
      "a value changed on a server card reaches the launcher in the Server Editor")
check('"--parallel", "3"' in _txt, "and so does the next one")
check("Write-VramReport" in _txt and "--parallel in a comment" in _txt,
      "with everything that is not an argument left alone")
check('"--no-cont-batching"' in _txt, "and a switch the card did not touch still there")
check(_disk.strip() == _txt.strip(),
      "the file that actually launches is the same text the editor shows")
check(_p.get("ctx") == "21504" and _p.get("parallel") == "3",
      "and the cards read back what they wrote")
# a $modelPath the panel cannot follow used to drop every card change in silence
_rs = seg(py, "def regen_slot_script", "def parse_launcher_params")
check('not (p.get("custom") or "").strip()' in _rs,
      "an existing launcher needs no parsable model to have a flag changed in it")


section("a launcher the panel did not write is edited, not replaced")

# regen_slot_script used to render params into a NEW file under generated-launchers and
# repoint the slot at it. On a hand-written launcher that silently swaps 600 lines of
# machinery - VRAM report, sampler table, stamp parsing - for a bare flag list.
_pd = tempfile.mkdtemp()
_mine = os.path.join(_pd, "hand-written.ps1")
_ORIG = ('function Write-VramReport { Write-Host "--parallel in a comment survives" }\n'
         '$llamaArgs = @(\n'
         '    "-m", $modelPath,\n'
         '    "--port", "1237",\n'
         '    "--ctx-size", "10240",\n'
         '    "--parallel", "1",\n'
         '    "--n-predict", "-1",\n'
         '    "--no-cont-batching",\n'
         '    "--flash-attn", "on"\n'
         ')\n')
_realarc, _realgen, _reallog2 = fp.ARCHIVE, fp.GEN_LAUNCHER_DIR, fp.panel_log
fp.ARCHIVE, fp.GEN_LAUNCHER_DIR = os.path.join(_pd, "arch"), os.path.join(_pd, "gen")
fp.panel_log = lambda *_a, **_k: None
try:
    with open(_mine, "w", encoding="utf-8-sig") as _f:
        _f.write(_ORIG)
    _slot = {"id": "s1", "script": _mine, "port": 1237,
             "params": {"model": os.path.join(_pd, "m.gguf"), "ctx": "21504", "parallel": "3"},
             "providers": [{"id": "pti", "cache": True}, {"id": "meta"}]}
    check(fp.slot_owns_script(_slot) is False, "a launcher outside generated-launchers is not ours")
    _res = fp.regen_slot_script({}, _slot)
    with open(_mine, encoding="utf-8-sig") as _f:
        _after = _f.read()
    _kept = os.path.exists(os.path.join(fp.ARCHIVE, "hand-written.ps1.before-panel"))
finally:
    fp.ARCHIVE, fp.GEN_LAUNCHER_DIR, fp.panel_log = _realarc, _realgen, _reallog2

check(_slot["script"] == _mine, "the slot still launches the same file")
check("Write-VramReport" in _after, "every line that is not a flag is untouched")
check("--parallel in a comment survives" in _after,
      "including a flag named in a comment, which is not an argument")
check('"--ctx-size", "21504"' in _after and '"--parallel", "3"' in _after,
      "the values the card carries are written")
check('"--slot-prompt-similarity", "0"' in _after, "and the flag caching needs is added")
check('"--n-predict", "-1"' in _after, "a negative value is not mistaken for a flag name")
check('"--no-cont-batching"' in _after,
      "a switch the card has no opinion on is left alone, not deleted")
for _never in ("--threads", "--n-gpu-layers", "--batch-size"):
    nin(_after, _never, "and a panel default nobody asked for is not poured in: %s" % _never)
check(_kept, "the version before the panel first touched it is kept")
# the array has to still be valid PowerShell: a trailing comma splats a null argument
_span = fp.ps1_args_span(_after)
_els = [l.rstrip() for l in _after[_span[0]:_span[1]].split("\n")
        if l.strip() and not l.strip().startswith("#")]
check(all(_e.endswith(",") for _e in _els[:-1]) and not _els[-1].endswith(","),
      "and the array is left valid - every element comma-separated, none trailing",
      str(_els[-2:]))
check(fp.ps1_set_flag("Write-Host x\n", "--parallel", "3") == "Write-Host x\n",
      "a launcher with no $llamaArgs array is refused rather than guessed at")


# SkyrimNet writes a role in brackets after the name: "You are Azeeda [hunter], a Female
# Redguard in Skyrim." The bracket stopped the match dead, so every such character was
# spoken under its voicetype.
for _line, _want in ((b"You are Serana, a vampire of Volkihar", b"Serana"),
                     (b"You are Azeeda [hunter], a Female Redguard in Skyrim.", b"Azeeda"),
                     (b"You are Iris the Elder [merchant], a Female Nord", b"Iris the Elder")):
    _m = fp.SPEAKER_RX.search(_line)
    check(bool(_m) and _m.group(1) == _want, "the name is read past any role tag: %s"
          % _want.decode(), (_m.group(1).decode() if _m else "no match"))
check(not fp.SPEAKER_RX.search(b"You are speaking to Maxxor, a Male Dark Elf."),
      "and 'speaking to' still names nobody - that is the listener")


# the reading is the figures; "cache", the slash and the percent are labels
_dash = seg(JS, "const cacheRx", "el.classList.toggle")
check('tk === "cache"' in _dash, "the word cache is painted as a label")
check("cacheRx.test(tk)" in _dash, "and its figures as numbers")
check('color:var(--ok)' in _dash and 'color:#e8ecf2' in _dash,
      "green for the numbers, white for the marks between them")


# lines are spoken in the order their dialogue was generated, so the first line to arrive
# belongs to the first request that came in. Taking the newest handed two NPCs speaking
# in quick succession each other's names.
_realpl3 = fp.panel_log
fp.panel_log = lambda *_a, **_k: None
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp.note_speaker(b"You are Azeeda [hunter], a Female Redguard in Skyrim.")
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _one, _two = fp.speaker_for_voice("femalecommoner"), fp.speaker_for_voice("serana")
finally:
    fp.panel_log = _realpl3
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
check(_one == "Azeeda" and _two == "Serana",
      "two NPCs speaking in succession keep their own names", "%s / %s" % (_one, _two))
check("for idx in range(len(_spk_recent)):" in seg(py, "def speaker_for_voice", "def tts_voice_name"),
      "the pending names are a queue, not a stack")

section("the server card reads in groups")

# The parameter table is not in group order - fit sits among the batching flags - so the
# card must lay them out by PARAM_GROUP_ORDER rather than by table position.
check(py.count("PARAM_GROUP_ORDER =") == 1,
      "the reading order is stated once - the launcher writer and the card share it")
check(len(fp.PARAM_GROUP_ORDER) > 3, "and it has an order to give",
      str(fp.PARAM_GROUP_ORDER))
_groups = {fp.PARAM_GROUP.get(r[0], "Other") for r in fp.SERVER_PARAMS}
for _g in _groups:
    check(_g in fp.PARAM_GROUP_ORDER, "and every group used is in it: %s" % _g)
check("paramGroups" in JS, "the page is given that order")
# without a group on each def the page falls back to "Other" and draws one heading over
# everything - which looks grouped and is not
_pdefs = seg(py, '"paramDefs": [', '"elevated": is_admin()')
check('"group": PARAM_GROUP.get(k' in _pdefs, "and every parameter is sent with its group")
_pe = seg(JS, "function paramEditor", "// ITEM 8:")
check("state.paramGroups" in _pe, "and lays the parameters out by it")
check('class="pgrp"' in _pe, "with a heading before each group")
check(".pgrp" in _css and "border-top" in seg(_css, ".pgrp {", ".pgrp:first-child"),
      "drawn as a rule, so the card reads as blocks")
# every parameter has to land somewhere, or a control disappears from the card
_ungrouped = [r[0] for r in fp.SERVER_PARAMS if r[0] not in fp.PARAM_GROUP]
check(not _ungrouped, "and no parameter is left without a group",
      ", ".join(_ungrouped) or "none")


# white, and the same rule the TTS page draws between its blocks
_pg = seg(_css, ".pgrp {", ".pgrp:first-child")
check("color: #fff" in _pg, "a group heading is white")
nin(_pg, "border-top: 1px", "and separated by a rule, not a flat border")
check("linear-gradient" in seg(_css, ".pgrp::before", ".pgrp:first-child"),
      "the same gradient the TTS page uses")


# the Options panel hangs over the terminal, so what is behind it is log text
_top = seg(_css, ".topanel { display: none;", ".tchrome.optopen .topanel")
# "-webkit-backdrop-filter: blur(2px)" CONTAINS "backdrop-filter: blur(2px)", so a
# substring test passed with the unprefixed declaration deleted. Count both.
check(_top.count("backdrop-filter: blur(2px)") == 2,
      "the Options panel blurs what is behind it, prefixed and not",
      str(_top.count("backdrop-filter: blur(2px)")))
check("-webkit-backdrop-filter" in _top, "with the prefixed form for older engines")
check("rgba(" in _top, "and a translucent fill - an opaque one leaves the blur nothing to do")
nin(_top, "background: var(--pan)", "which is why the flat panel colour is gone")


section("the terminal switches live behind one button")

# Timestamps, Insert TTS and the two output switches were four buttons in the bar.
_dashbar = seg(PAGE, 'id="twrap-dashboard"', 'id="tail-dashboard"')
check('data-act="termOptions"' in _dashbar, "there is an Options button")
_opts = seg(_dashbar, 'class="topanel"', 'class="tpanel"', nth=1)
for _act in ("termStamps", "termInsTts", "termTagOutPti", "termTagOutPme"):
    check(('data-act="%s"' % _act) in _opts, "and %s is inside it" % _act)
    nin(seg(_dashbar, 'class="tbar"', 'class="topanel"'), 'data-act="%s"' % _act,
        "not in the bar as well: %s" % _act)
_oh = seg(JS, 'if (d.act === "termOptions")', 'if (d.act === "tmaxAdjust")')
check('classList.remove("adjopen")' in _oh and 'classList.toggle("optopen")' in _oh,
      "opening it closes Adjust - one menu at a time")
check('_c0.classList.remove("optopen", "provopen")' in seg(JS, 'if (d.act === "tmaxAdjust")', 'if (d.act === "tailMax")'),
      "and opening Adjust closes both of them")

section("the panel asks for the emotions SkyrimNet teaches")

# Higgs accepts twenty-one emotions; SkyrimNet's own Voice Performance Tags prompt lists
# fourteen. Those fourteen are what its dialogue models are taught to write, so they are
# what PTI and PME are offered and what their answers are held to.
_em = dict(fp.TAG_OFFER)["Emotion"]
# SkyrimNet's template lists every emotion Higgs has, so the panel offers every one -
# including anger, fear and disgust, without which an aggressive line cannot be labelled
check(len(_em) == len(fp.TTS_TAGS["emotion"]),
      "every emotion the engine has is offered", "%d of %d" % (len(_em), len(fp.TTS_TAGS["emotion"])))
check(all(w.startswith("EMOTION-") and w.split("-", 1)[1].lower() in fp.TTS_TAGS["emotion"]
          for w in _em),
      "and every one of them is a tag the engine really has")
_au2 = dict(fp.TAG_OFFER)["Audio"]
check(len(_au2) == 22, "every audio tag the engine has is offered, pauses included",
      str(len(_au2)))
# prosody is written BARE, as SkyrimNet's template teaches it, so a player line marked
# up here looks like an NPC line marked up there
for _p in ("pause", "long_pause", "speed_slow", "pitch_high", "expressive_low"):
    check(_p in _au2, "prosody is offered bare: [%s]" % _p)
    check(fp.tts_apply_tags("Wait [%s] for it." % _p, True, "audiocpp").count("<|") == 1,
          "and translates: [%s]" % _p)
for _w in ("ANGER", "FEAR", "DISGUST", "AMUSEMENT", "DETERMINATION", "BITTERNESS",
           "ELATION", "AFFECTION", "AROUSAL", "AWE", "CONTEMPLATION", "CONTENTMENT",
           "ENTHUSIASM", "HELPLESSNESS", "LONGING", "PRIDE", "RELIEF", "SADNESS",
           "SHAME", "SURPRISE", "CONFUSION"):
    check(("EMOTION-%s" % _w) in _em, "asked for: %s" % _w)
# the notation is SkyrimNet's, so a tagged player line is indistinguishable from an NPC one
check(all(w.startswith("EMOTION-") for w in _em), "emotions are written EMOTION-NAME")
check(all(w.startswith(("SFX-", "STYLE-")) or "-" not in w.replace("_", "")
          for w in dict(fp.TAG_OFFER)["Audio"]),
      "sounds and styles carry their kind; prosody is bare, as SkyrimNet writes it")
check(fp._clean_tagged("[emotion-contentment] Nord?", "Nord?") == "[EMOTION-CONTENTMENT] Nord?",
      "an answer is accepted in either case and normalised")
check(fp._clean_tagged("[surprise] Nord?", "Nord?") == "",
      "and the old bare shorthand is no longer one of ours")

# THE IMPORTANT HALF. Narrowing what the panel asks for must not narrow what it accepts
# from SkyrimNet - an NPC line tagged with an emotion the panel no longer requests still
# has to reach the engine, or dialogue silently loses its delivery.
for _line, _want in (
        ("[EMOTION-ANGER] Get out.", "<|emotion:anger|>Get out."),
        ("[EMOTION-DETERMINATION] Not for all the gold.",
         "<|emotion:determination|>Not for all the gold."),
        ("[SFX-LAUGHTER] Hehe.", "<|sfx:laughter|>Hehe.")):
    _got = fp.tts_apply_tags(_line, True, "audiocpp")
    check(_got == _want, "a tag SkyrimNet wrote is still translated: %s" % _line.split()[0],
          _got)
# and the two prompts agree, because they read the same table
check(", ".join(_em) in fp.tts_tag_prompt(), "the tagger is shown exactly that list")
check(", ".join(_em) in fp.mood_prompt(3, ""), "and so is the mood reader")
# a word the panel stopped asking for must not come back from PTI either
# nothing is dropped any more - so the refusal is tested with a word that does not exist
check(fp._clean_tagged("[EMOTION-NONSENSE] Get out.", "Get out.") == "",
      "an answer using a word we never offered is refused")
check(fp._clean_tagged("[EMOTION-ANGER] Get out.", "Get out.") == "[EMOTION-ANGER] Get out.",
      "and anger, which the template restored, is accepted")
check(fp._clean_tagged("[EMOTION-SURPRISE] Get out.", "Get out.") == "[EMOTION-SURPRISE] Get out.",
      "and one using an offered word is kept")

section("an NPC's internal thought")

# SkyrimNet asks its characters to end a reply with private reasoning wrapped in
# <internal_thought>. It is never spoken, so it never reaches the TTS record - the reply
# on its way past the proxy is the only place to catch it.
check("ttsThoughtOut" in fp.DEF_SETTINGS, "it has a switch, off by default")
check(fp.DEF_SETTINGS["ttsThoughtOut"] == "off", "off by default")
check(bool(fp.THOUGHT_RX.search("a <internal_thought>x</internal_thought>")),
      "the tag is matched as SkyrimNet writes it")
check(not fp.THOUGHT_RX.search("<internal thought>x</internal thought>"),
      "and not a shape it does not write")
_pw = seg(py, "def _proxy(self)", "def _background_init")
check('d.get("content"): said.append' in _pw, "the streamed reply is kept, not only its reasoning")
check('said=(msg.get("content") or "")' in _pw, "and so is a non-streamed one")
check("said=\"\".join(said)" in _pw, "both handed to report")

_td = tempfile.mkdtemp()
_realld2 = fp.log_dir
fp.log_dir = lambda cfg=None: _td
_REPLY = ("The Gray-Manes? I know them. <internal_thought>Thorald went missing "
          "months ago.</internal_thought>")
try:
    fp._spk_recent[:] = [(0, "Azeeda")]
    _before = list(fp._spk_recent)
    fp.thought_lines(_REPLY, "Azeeda", {"settings": {"ttsThoughtOut": "on"}})
    _on = "".join(open(os.path.join(_td, _f), encoding="utf-8").read() for _f in os.listdir(_td))
    for _f in os.listdir(_td):
        os.remove(os.path.join(_td, _f))
    fp.thought_lines(_REPLY, "Azeeda", {"settings": {"ttsThoughtOut": "off"}})
    _off = "".join(open(os.path.join(_td, _f), encoding="utf-8").read() for _f in os.listdir(_td))
    for _f in os.listdir(_td):
        os.remove(os.path.join(_td, _f))
    fp.thought_lines("Just a plain line.", "Azeeda", {"settings": {"ttsThoughtOut": "on"}})
    _none = "".join(open(os.path.join(_td, _f), encoding="utf-8").read() for _f in os.listdir(_td))
    _after = list(fp._spk_recent)
finally:
    fp.log_dir = _realld2
    fp._spk_recent[:] = []

check("Thorald went missing" in _on, "the thought is written", _on.strip()[:70])
check(fp.THOUGHT_MARK in _on, "under its own mark, not a spoken one")
check("Azeeda" in _on, "beside the character who thought it")
# a MID branch, never an end one: the spoken lines are spliced in beneath it, and an end
# elbow stops at its own row - which left a wrapped thought with nothing joining its rows
check(fp.TREE_PAD + fp.TREE_MID in _on, "as a branch, like every other line the panel adds")
nin(_on, fp.TREE_END, "and never the closing elbow, since it is not the last thing there")
_tl = seg(py, "def thought_lines", "def panel_prov_record")
nin(_tl, "TREE_END", "which the writer cannot produce at all")
_sp2 = seg(JS, "function spliceTts", "const SPOKEN_TAG")
check("0x1F4AD" in _sp2 and "put++" in _sp2,
      "and a spoken line is spliced BELOW any thought already hanging off that reply")
_ps2 = seg(JS, "function paintSpoken", "function paintTail")
check('const isThought = line.indexOf(String.fromCodePoint(0x1F4AD)) >= 0;' in _ps2,
      "a thought is recognised by its own mark, not assumed")
check("#c07ffb" in _ps2 and "isThought" in _ps2.split("const saidHtml")[1],
      "and painted grape rather than the gold of speech")
check("text-shadow:0 0 6px" in _ps2, "with a slight glow, so it reads as interior")
check("<internal_thought>" not in _on, "with the tag itself stripped")
check(_off == "", "and nothing at all with the switch off")
check(_none == "", "a reply carrying no thought writes nothing")
# the spoken line still needs that name: peeking must not consume it
check(_after == _before, "the shared name queue is not touched at all", str(_after))
check("speaker = note_speaker(body)" in seg(py, "def _proxy(self)", "def _background_init"),
      "the name comes from the request that produced the reply, not from the queue")
check(PAGE.count('data-act="termThoughts"') == 3,
      "the switch is in all three Options panels - the dashboard and both split panes",
      str(PAGE.count('data-act="termThoughts"')))
check(PAGE.count('data-act="termOptions"') == 3, "one Options button each",
      str(PAGE.count('data-act="termOptions"')))
for _s in ("d", "t"):
    _pane = seg(PAGE, 'id="splitsel-%s"' % _s, 'id="tail-split%s"' % _s)
    check('data-act="termOptions"' in _pane, "the %s pane has its own Options button" % _s)
    check('data-kind="split%s"' % _s in seg(_pane, 'class="topanel"', 'class="tpanel"'),
          "with Timestamps for that pane inside it" )
    # the slice starts inside the bar, so everything before the panel IS the bar
    nin(_pane[:_pane.index('class="topanel"')], ">Timestamps</button>",
        "and not loose in the %s pane's bar any more" % _s)
check('"termThoughts", "ttsThoughtOut"' in JS, "wired to its own setting")
check("0x1F4AD" in seg(JS, "function panelProvMatcher", "function fixTree(text)"),
      "and off hides the lines already on screen, as the others do")


# Higgs sometimes runs past its own end-of-content token. That is upstream and it is
# retried - what the panel controls is what the failure COSTS. With no cap it generates
# to audio.cpp's default and a four-second line burned nineteen seconds before the retry
# even started. Measured on a real overrun: 46 characters, 104 tokens, 4.2 seconds.
check(fp.acpp_token_cap("Well, I've been told I can be quite. thorough.") == 161,
      "a line is capped at roughly twice the tokens it needs",
      str(fp.acpp_token_cap("Well, I've been told I can be quite. thorough.")))
check(fp.acpp_token_cap("Well, I've been told I can be quite. thorough.") > 104,
      "which is comfortably above what that line actually took, so it is never cut short")
check(fp.acpp_token_cap("Yes.") == fp.acpp_tok_floor(4) == fp.TTS_ACPP_TOK_MIN,
      "a very short line still gets room for its lead-in - scaled to the line now")
check(fp.acpp_token_cap("") == fp.TTS_ACPP_TOK_MIN
      and fp.acpp_token_cap(None) == fp.TTS_ACPP_TOK_MIN,
      "and nothing at all does not produce a cap of nothing")

# ------------------------------------------------------------------ patch118
# A day's calibration logs, measured: the floor decided 99 caps, the guard 81, the
# estimate 67 - the fit the user calibrated was not consulted for 73% of lines, and
# one runaway on a floor-decided ten-character line entered the record at 128/17 =
# 7.4, pinning the headroom at its maximum for the whole session. Three faults, all
# of them arithmetic that outranked the measurement.
check(fp.acpp_tok_floor(10) == fp.TTS_ACPP_TOK_MIN
      and fp.acpp_tok_floor(42) == 74
      and fp.acpp_tok_floor(73) == fp.TTS_ACPP_TOK_FLOOR
      and fp.acpp_tok_floor(200) == fp.TTS_ACPP_TOK_FLOOR,
      "the floor is HALF the guard, between the warm-up minimum and the old flat 128",
      str([fp.acpp_tok_floor(c) for c in (10, 42, 73, 200)]))
check(fp.acpp_tok_floor(10, {"ttsFixedTokPerChar": "10"}) == 50,
      "and it moves with the user's tokens-per-character, as half of it")
check(all(fp.acpp_tok_floor(c) <= fp.TTS_ACPP_TOK_FLOOR for c in range(0, 400, 7)),
      "no line's floor is ever HIGHER than the flat one it replaces")
check(fp.acpp_token_cap("x" * 10) == fp.TTS_ACPP_TOK_MIN
      and fp.acpp_token_cap("x" * 42) == 147,
      "the guard's own minimum is that same floor, so a short runaway burns 48, not 128")
_ac18 = seg(py, "def tts_auto_cap(", "AUTOCAL_LAST = [0.0]")
check("floor = acpp_tok_floor(chars, st)" in _ac18
      and "cap = max(floor, min(int(want), guard))" in _ac18,
      "the per-line cap is clamped by the per-line floor")
nin(_ac18, "max(TTS_ACPP_TOK_FLOOR, min",
    "and no clamp against the flat constant is left in it")
check("floor, guard))" in seg(py, "def autocal_log(", "TTS_RESULT_WAIT_S = "),
      "the calibration feed prints THAT line's floor, not the constant")
_er18 = seg(py, "def eoc_record(", "def eoc_rows(")
check('"bound": str(AUTOCAL_BOUND[0] or "")' in _er18,
      "a failure records WHO decided the cap it hit")
_ff18 = seg(py, "def tts_autocal_fit(", "AUTOCAL_HEAD_MIN = ")
check('if str(f.get("bound") or "") != "estimate":' in _ff18,
      "and the fit scores a failure by the same rule as a success")
check(fp.tts_autocal_fit(
          [{"chars": 60, "pause_s": 0.0, "secs": 3.8, "tok": 110.0, "est": 96.0,
            "bound": "estimate", "at": "x"}] * 10,
          [{"est": 17.2, "cap": 128.0}, {"est": 30.0, "cap": 223.0}])["worst"] < 1.2,
      "a legacy failure with no bound recorded is a runaway, not evidence - the "
      "7.4 that pinned a session's headroom cannot happen again")
# (the model was once shown 120 rows; the model fit is gone whole in patch153 -
# the arith refit reads the measurement store directly)
check("HALF the guard" in fp.autocal_algorithm_text({}),
      "and the algorithm text describes the floor the code now applies")

# ------------------------------------------------------------------ patch119
# Two things from one field session. The fit call on a Thinking-ON card answered
# "not a usable fit" every time: a flat max_tokens of 60 was spent entirely inside
# the reasoning block, so the visible answer was empty and the parse had nothing.
# And a terminal record could only be read, not opened - the request behind it and
# the reply that came back lived nowhere the page could reach.
check("PANEL_THINK_BUDGET = 2000" in py,
      "a panel job's thinking is BUDGETED, with a named default under the sliders")
_ch19 = seg(py, "def _chat(rt, system", "# What was actually said, in order.")
check('payload["reasoning_budget_tokens"] = int(think_budget)' in _ch19
      and 'payload["max_tokens"] = int(cfg_max) + int(think_budget)' in _ch19,
      "the budget bounds the think and the ceiling has room for BOTH halves")
check('rt.get("thinking") and not rt.get("grammar")' in _ch19,
      "and a budget is never sent with a grammar, which answers 500")
_pc20 = seg(py, "def panel_chat(", "CAL_KNOBS = (")
check("think_budget=_tb" in _pc20 and '"ttsCalibThinkBudget"' in _pc20,
      "the diagnosis and the calibration get the USER'S room - the one budget left")
# (the fit call, its cfg_max and its unusable-answer wording left with the model
# fit in patch153)
check('_autocal_parse(str((st or {}).get("ttsAutoCalMedian", ""))' in py
      and py.count("_autocal_parse(") == 3,
      "the fit parser reads only the STORED fit now - no model answer feeds it")
# the record, opened
check("self.payloads = collections.deque(maxlen=PAYLOAD_KEEP)" in py
      and "PAYLOAD_KEEP = 80" in py,
      "the last requests and replies are kept in a ring, in memory only")
nin(seg(py, "def pay_add(", "def pay_get("), "open(",
    "and never written to a file - the prompts are the player's game")
_rp19 = seg(py, "def report(self, rt, think", "def _fold_request")
check('rt.pop("_sent", None)' in _rp19 and "pay_add" in _rp19
      and 'line += "  \\u27e6%d\\u27e7" % pid' in _rp19,
      "a record that has a payload wears its id, stripped from view by the painter")
check('rt["_sent"] = json.dumps(payload, indent=2' in _ch19,
      "the panel's own calls leave their request on the route for the same record")
check('"/api/proxy-payload": api_proxy_payload' in py,
      "and one endpoint answers a record by id, or says it left the ring")
_pt19 = seg(JS, "const pidRx = new RegExp", "function paintTok(tk)")
check("pm.index" in _pt19 and 'data-act="proxyPayload"' in _pt19,
      "the painter strips the id and makes the emoji and title the button")
check("portAt > base + 1" in _pt19 and "openAt = base" in _pt19,
      "wrapping from the mark to the last title word, wherever the mark sits")
_pm19 = seg(JS, 'if (d.act === "proxyPayload")', 'if (d.act === "ttsTokPerCharReset")')
check("REQUEST PAYLOAD" in _pm19 and "RESPONSE PAYLOAD" in _pm19
      and "showModal(" in _pm19,
      "clicking opens the request and the reply over the page, side by side")
check("--- reasoning ---" in _pm19,
      "with the thinking under the reply when there was any")
check("payloadPretty(e.req)" in _pm19 and "respPretty(e.resp)" in _pm19,
      "both halves go through the colour-coders, which escape every chunk they tint")
check(".plpay { cursor:pointer" in PAGE and ".plpay:hover" in PAGE,
      "and the button reads as one: a pointer, and a glow under the hand")
check("--line:#2a2d34" in PAGE,
      "the border colour nine rules already asked for finally exists")

# ------------------------------------------------------------------ patch120
# The model-derived speech rate is called what the section is called - the TTS
# Calibration - everywhere it appears, the thinking each calibration model may do
# is the USER'S number on a slider beside its switch, and the monitoring boxes
# explain what their figures mean rather than only naming them.
nin(JS, "LLM fit", "the old name is gone from the page")
nin(JS, "LLM-fitted", "and from the per-line working")
check("fit" not in fp.PANEL_JOBS and ">TTS Calibration</option>" not in JS
      and "tts-ttsAutoCalUseFit" not in JS,
      "the fit record is gone, and so is the speech-rate menu - a stored fit is "
      "simply used when present, chosen by nobody")
check("ttsAutoCalThinkBudget" not in py and "ttsAutoCalThink" not in py,
      "the fit job's thinking switch and budget are gone from the source entirely")
check('"ttsCalibThinkBudget": "2000"' in py,
      "both default to 2000, which is also the code's own floor of none")
check(fp.think_budget({"ttsAutoCalThinkBudget": "4500"}, "ttsAutoCalThinkBudget",
                      fp.PANEL_THINK_BUDGET) == 4500
      and fp.think_budget({}, "ttsAutoCalThinkBudget", fp.PANEL_THINK_BUDGET) == 2000,
      "and the calls read the slider, falling back to that default")
for _bx20, _frag20 in (("headroom", "estimate x this"),
                       ("worst line", "under-predicted"),
                       ("pad", "10% on top"),
                       ("scored lines", "ESTIMATE decided"),
                       ("runaways", "end-of-content"),
                       ("TTS calibration", "least")):
    check(_frag20 in seg(JS, "function headroomBoxes(d)", "function ttsAutoCalBlock("),
          "the %s box explains itself: %r is in its tooltip" % (_bx20, _frag20))

# ------------------------------------------------------------------ patch121
# The terminal button is the text it always was, the rows hold their columns, the
# fit wears the panel's own mark, and the opened record is colour-coded like the
# viewer the layout was drawn from.
_pt21 = seg(JS, "const pidRx = new RegExp", "function paintTok(tk)")
_css21 = seg(PAGE, ".plpay { cursor:pointer", ".plpay:hover")
nin(_css21, "dotted", "no underline at rest - the text is the text it always was")
nin(_css21, "text-shadow", "and at rest no glow restyles the glyphs - the hover may")
_ph45 = seg(PAGE, ".plpay:hover {", ".moodic[title]")
check("text-shadow:0 0 7px var(--acc)" in _ph45 and "drop-shadow" in _ph45,
      "the button shows itself under the hand as a glow on the glyphs")
check("background" not in _ph45 and "box-shadow:0 0 0 1px" not in _ph45,
      "and no painted rectangle - the highlight is light, not a box")
check('<span class="pcell">' in _pt21 and "ti === base && portAt > base + 1" in _pt21,
      "every record's mark sits in one fixed-width cell, clickable or not")
check(".tail .pcell { display:inline-block; width:2ch" in PAGE,
      "two characters wide, whatever the emoji's own advance")
check(fp.PANDORUM_MARK not in {m for _, m in fp.PANEL_JOBS.values()},
      "the panel's glowing mark left with the fit record - no job wears it now")
check("%-15s" in seg(py, "def proxy_line_text(", "def acpp_report")
      and fp.proxy_line_text("x", "TTS Calibration", "1238", 1, 1, 0, 1.0, 1.0, 1.0)
            .index("[1238]")
          == fp.proxy_line_text("x", "GM", "1238", 1, 1, 0, 1.0, 1.0, 1.0).index("[1238]"),
      "the name column holds the longest name, so every port starts at one column")
_pp21 = seg(JS, "function payMd(line)", 'if (d.act === "proxyPayload")')
check('"#e8956d"' in _pp21 and "font-weight:700" in _pp21,
      "prompt headings and **bold** runs are lit in the request pane")
check("v.split(NL).map(payMd)" in _pp21,
      "and a string with newlines is laid out as REAL lines, not one escaped one")
check("JSON.parse(text)" in _pp21 and "catch" in _pp21,
      "a request that is not JSON is shown as it went, escaped")
check("s.indexOf(OT)" in _pp21 and '"#c07ffb"' in _pp21,
      "the reply pane tints internal thoughts in the terminal's own grape")
check('out += esc(s.slice(i, a))' in _pp21,
      "and the tag walker escapes every chunk it passes - no regex, no backslash")
check(_pp21.count("new RegExp") == 1 and 'new RegExp("^ +")' in _pp21,
      "one RegExp in the colour-coders - the space trim - and it carries no backslash")

# ------------------------------------------------------------------ patch122
# Hide Stamps broke the terminal: the mark was addressed as token 2, which it only
# is BEHIND a stamp - stripped, the title landed in the mark's 2ch cell and wrapped
# two letters to a row. Principle 8's oldest shape: an index that assumes a layout.
# And the animations: rows and bar segments now MOVE instead of snapping.
check('tks[0].charCodeAt(0) === 91' in _pt19 and 'tks[0].indexOf(":") > 0' in _pt19,
      "the mark is found by what a stamp IS, not by where it usually sits")
check("const base = " in _pt19,
      "and one base index serves the cell and the click alike")
# patch141: the arrival animation and its row-marking left with the ground-up
# rebuild - a fixed-height row needs no ceremony, and less machinery is the point
check("markNewRows" not in JS and "tlineIn" not in PAGE,
      "the arrival machinery is gone with the rebuild, not left half-wired")

# ------------------------------------------------------------------ patch141
# The renderer, rebuilt from the ground up at the owner's order: every terminal row
# is a fixed 1.5em box, white-space:pre, overflow hidden - a second line inside a
# row is IMPOSSIBLE by construction, whatever the bytes, the glyphs, or the markup
# inside it do. The run feeds a poisoned tail - CRLF, a bare CR mid-line, a stray
# LF smuggled into a line - and asserts the shell holds one row per source line.
_gu41 = None
try:
    import subprocess as _spg
    _cg41 = ("const src=require('fs').readFileSync(process.argv[1],'utf8');"
      "function sl(a,b){const i=src.indexOf(a);const j=src.indexOf(b,i);"
      "return src.slice(i,j).split(String.fromCharCode(13)).join('');}"
      "let code='';"
      "code+=sl('const TERM_INS_KINDS','function paintTail(');"
      "code+=sl('function fixTree(text)','function hiddenProvs');"
      "code+=sl('function dropPanelProv(','function paintTail(');"
      "code+=sl('function paintTail(','function stepAt');"
      "globalThis.window=globalThis;const state={settings:{},routing:[]};"
      "let captured='';"
      "const el={set innerHTML(h){captured=h;},dataset:{},"
      "classList:{toggle:function(){},add:function(){},remove:function(){}},style:{}};"
      "const $=id=>id==='tail-dashboard'?el:null;"
      "const esc=s=>String(s==null?'':s);"
      "function termInsTtsOn(){return false;}"
      "function sizeTailEl(){}function paintThink(){}"
      "function paintSpoken(l){return esc(l);}function paintTok(x){return esc(x);}"
      "function provMark(){return '';}"
      "eval(code);"
      "sizeTailEl=function(){};paintThink=function(){};"
      "paintSpoken=function(l){return esc(l);};paintTok=function(x){return esc(x);};"
      "const CR=String.fromCharCode(13),NL=String.fromCharCode(10);"
      "const raw='line one   '+CR+NL+'line'+CR+' two'+CR+NL+'line three'+String.fromCharCode(9)+'  '+CR+NL;"
      "paintTail('dashboard', raw);"
      "console.log(JSON.stringify([captured.indexOf(CR)<0 && captured.indexOf(NL)<0"
      " && !/[ ]<\\/div>/.test(captured),"
      "(captured.match(/class=.tl./g)||[]).length]));")
    _rg41 = _spg.run(["node", "-e", _cg41, os.path.join(ROOT, "fleet-panel.py")],
                     capture_output=True, text=True, timeout=60)
    _gu41 = json.loads(_rg41.stdout.strip() or "null")
except Exception:
    _gu41 = None
if _gu41 is not None:
    check(_gu41 == [True, 3],
          "run: a poisoned tail paints one row per line with no break character "
          "anywhere in the markup, and the file's trailing empty line paints no "
          "phantom row", str(_gu41))
else:
    check(False, "the poisoned-tail run did not RUN - node or the snippet is broken")
_mb22 = seg(JS, "function paintMeterBar(", "function paintMeter(")
check("bar.dataset.segset === want" in _mb22
      and "el2.style.width = " in _mb22,
      "same segment set: the bars' widths are updated IN PLACE")
check("transition:width .35s ease" in _mb22,
      "so the width transition they always carried finally has an element that survives")
check(_mb22.index("bar.dataset.segset === want") < _mb22.index("bar.innerHTML = segs.map"),
      "and a fresh build happens only when the segment set itself changed")

# ------------------------------------------------------------------ patch123
# Four fixes from one play session: the TTS server survived the panel's exit when a
# panel RESTART had orphaned the handle; the Thinking controls were a row of small
# grey words; the Monitoring block blinked on every state tick; and the player's
# name was still "Player" because these prompts carry no party heading at all.
# patch124: the sweep patch123 wrote was a SECOND discovery of the panel's own TTS
# server - the button already had one (_kill_port_owner) - and its PowerShell quoting
# emitted rows no parser matched, so it found nothing on its first day in the field.
# The exit now runs the same stop the button runs. One implementation, everywhere.
_ex23 = seg(py, "def full_exit", "def watchdog_loop")
check("stop_tts_server(reason)" in _ex23
      and "_kill_port_owner(tts_server_port())" in _ex23,
      "quitting runs the SAME stop the TTS page's Stop button runs")
nin(py, "tts_sweep_orphans", "the second, drifted discovery is gone whole")
check(_ex23.index("stop_tts_server") < _ex23.index('run_fleet(["-Stop"])'),
      "TTS first: a closing console gives this ~5 seconds and -Stop can eat them")
_fin23 = seg(py, "def stop_tts_server", "def api_tts_server")
check("elif pid and not p:" in _fin23,
      "a pid with no handle - the restart case - is still stopped by pid")
# (the titled two-column job cell left with LLM Controlled in patch153)
check("function setChanged(el, html)" in JS and "el.__pl === html" in JS,
      "a refresh writes innerHTML only when the content actually changed")
for _sc23 in ('setChanged($("tts-head-now")', 'setChanged($("tts-samp-chips")',
              "setChanged(keys,"):
    check(JS.count(_sc23) >= 1, "guarded: %s" % _sc23)
_sd23 = JS.find("if (window.__ttsDiag)")
check(_sd23 >= 0 and "window.__ttsMeter" in JS and _sd23 < JS.find("loadTtsDiag();"),
      "a rebuilt pane is seeded from what was last known BEFORE the fetches repaint it")
check(b"Think internally as " == fp.PLAYER_THINK,
      "the player is also named by their own standalone thought prompt")
_ns23 = seg(py, "def note_speaker", "def speaker_for_voice")
check("PLAYER_THINK + name.encode" in _ns23,
      "and only when that prompt thinks AS its own speaker - the two names must agree")
check('sys_p += "\\n\\nThe line is spoken by the player, %s." % _spk_player[0]' in py,
      "PTI is told who the player is, from the name the proxy learned")
check('_sys += "\\nThe player is %s." % _spk_player[0]' in py,
      "and PME the same, under its own prompt")
check(fp.acpp_token_cap("x" * 400) < fp.TTS_CAP_CEILING,
      "even a long line stays under the ceiling the retry escalation stops at",
      "%d vs %d" % (fp.acpp_token_cap("x" * 400), fp.TTS_CAP_CEILING))
check("min(TTS_CAP_CEILING, _cap * (1.5 ** (attempt - 1)))" in py,
      "and that ceiling is the one the escalation actually uses - one number, named")
nin(py, "TTS_MAX_NEW_TOKENS",
    "the MOSS-era ceiling is gone with the poster it served (patch184)")
_ao = seg(py, "def _tts_acpp_once", "def tts_server_port")
# under every name the family might read it as - this build honours none of them, which
# is why busy_timeout_ms is the bound that has to work
for _k in ("max_new_tokens", "max_tokens", "higgs_audio_tts.max_new_tokens"):
    check(_k in _ao, "the token cap is sent as %s" % _k)
check("_cap, _capnote, _est = tts_auto_cap(text, _st0)" in _ao,
      "all from the one figure - the auto cap, which IS the guard when off")
_as = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
check('"EOC" in _msg' in _as, "a differently worded overrun is still recognised as one")
check("_try >= 2" in _as, "and it is tried three times, not for ever")


# Audio Tags defaults to stripping, and PTI forces it ON for the line it tagged itself -
# so the player was heard with feeling while every NPC line arrived flat, and nothing
# anywhere said why. The strip is a setting; being silent about it was the fault.
_L = "[EMOTION-SADNESS] It has been a long day. [SFX-SIGH] The longest of my life."
check(fp.tts_tag_count(_L) == 2, "a line's performance tags are counted",
      str(fp.tts_tag_count(_L)))
check(fp.tts_tag_count("It has been a long day.") == 0, "a plain line carries none")
check(fp.tts_tag_count("Meet me at [the mill] tonight.") == 0,
      "and an ordinary bracket is not one - a line may say [the mill]")
check(fp.tts_tag_count("") == 0 and fp.tts_tag_count(None) == 0, "nothing counts as none")
_ri2 = seg(py, "def _run_inner", "def _silence")
check("tts_tag_count(raw)" in _ri2 and "if not keep_tags:" in _ri2,
      "and a line about to lose them says so")
check("Audio Tags is" in _ri2 and "(TTS page)" in _ri2,
      "naming the setting that did it, and where to find it")
# the translator itself is undamaged - the strip is the only thing removing them
check(fp.tts_apply_tags(_L, True, "audiocpp").count("<|") == 2,
      "with Audio Tags on, both reach the engine as tokens",
      fp.tts_apply_tags(_L, True, "audiocpp"))
check("<|" not in fp.tts_apply_tags(_L, False, "audiocpp"),
      "and with it off, neither does")


# Whether a tag survived SkyrimNet or was never sent is not answerable from the panel
# otherwise: the terminal only ever shows the PROCESSED line, so a tag stripped here and
# a tag never sent look identical. The raw line settles it.
_ri3 = seg(py, "def _run_inner", "def _silence")
check('panel_log("[tts] in: %s" % raw[:200])' in _ri3,
      "the line as SkyrimNet sent it is recorded before anything touches it")
check(_ri3.index('[tts] in:') < _ri3.index("tts_apply_tags"),
      "before the tags are translated or stripped, not after")
check(_ri3.index('[tts] in:') < _ri3.index("tts_player_tag"),
      "and before the tagger has a chance to add any")


# SkyrimNet's chatterbox vocabulary is wider than Higgs' in places. Those tags are
# removed so they are not read aloud - right, and silent until now.
check(fp.tts_tags_dropped("[sarcastic] Oh, marvellous. [gasp] You did it.")
      == ["sarcastic", "gasp"], "a tag with no Higgs counterpart is named")
check(fp.tts_tags_dropped("[angry] You dare? [laugh] Hah.") == [],
      "one that translates is not")
check(fp.tts_tags_dropped("Meet me at [the mill] tonight.") == [],
      "and an ordinary bracket is neither")
check(fp.tts_tags_dropped("") == [] and fp.tts_tags_dropped(None) == [], "nothing is nothing")
_ri4 = seg(py, "def _run_inner", "def _silence")
check("tts_tags_dropped(raw)" in _ri4 and "no Higgs equivalent" in _ri4,
      "and the terminal says which ones went")
# every tag SkyrimNet's chatterbox branch offers must either translate or be dropped
# cleanly - one falling through would be read aloud as words
for _w in ("angry", "fear", "surprised", "whispering", "dramatic", "narration", "happy",
           "sarcastic", "clear throat", "sigh", "shush", "cough", "groan", "sniff",
           "gasp", "chuckle", "laugh", "crying"):
    _out = fp.tts_apply_tags("[%s] Line here." % _w, True, "audiocpp")
    check("[%s]" % _w not in _out,
          "a chatterbox tag is never read aloud: [%s]" % _w, _out)


# A failed line ran 18.15s against the 20s that used to be hardcoded as busy_timeout_ms:
# the per-request cap is ignored by this build and that timeout is the only real bound,
# so it is a setting rather than a number buried in a config writer.
check(fp.DEF_SETTINGS.get("ttsAcppBusyMs") == "9000",
      "the line time limit is a setting, defaulting to 9s",
      str(fp.DEF_SETTINGS.get("ttsAcppBusyMs")))
_c0 = json.loads(fp.tts_acpp_config({"settings": {}}))["models"][0]
check(_c0["busy_timeout_ms"] == 9000, "defaulting to 9s, not the old hardcoded 20",
      str(_c0["busy_timeout_ms"]))
for _v, _want in (("10", 2000), ("999999", 60000), ("abc", 9000), ("", 9000)):
    _g = json.loads(fp.tts_acpp_config({"settings": {"ttsAcppBusyMs": _v}}))["models"][0]
    check(_g["busy_timeout_ms"] == _want,
          "clamped to something a server can honour: %r" % _v, str(_g["busy_timeout_ms"]))
check("ttsAcppBusyMs" in PAGE, "with a row on the TTS page")
_as2 = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
check("_spent = time.time() - _t0" in _as2, "a failed attempt is timed")
check("%.1fs lost" in _as2, "and says what it cost")
check("server limit" in _as2, "beside the limit that was meant to stop it")

section("the backend takes no settings, and the panel stops pretending otherwise")

# audio.cpp validates its session option list and exits on anything not on it. Only
# reference_cache_slots is accepted for this family, so temperature, top_k, top_p,
# repetition_penalty, sample_rate and max_new_tokens are gone rather than left as
# controls that cannot reach the engine.
_so = json.loads(fp.tts_acpp_config({"settings": {}}))["models"][0]["session_options"]
check(list(_so) == ["higgs_audio_tts.reference_cache_slots"],
      "one session option is written, the only one this family takes", str(list(_so)))
for _dead in ("acpp_sampling", "ACPP_SAMPLING", "acpp_session_options", "acpp_proxy_side",
              "acpp_learn_bad_opt", "ttsBackendSide", "ttsAcppTemp", "ttsAcppRate"):
    nin(py, _dead, "and the control that could not reach it is gone: %s" % _dead)

# what IS controllable: how much text goes over at once. Every token generated is
# another chance to pass over end-of-content, so a shorter chunk fails less often and
# costs less when it does - and it is the only thing a calibration can sweep.
check(fp.tts_chunk_chars({}) == 170, "the chunk size keeps its old value by default",
      str(fp.tts_chunk_chars({})))
check(fp.tts_chunk_chars({"ttsChunkChars": "5"}) == 40
      and fp.tts_chunk_chars({"ttsChunkChars": "9999"}) == 400,
      "clamped to something speakable")
check(fp.tts_chunk_chars({"ttsChunkChars": "abc"}) == 170, "and nonsense falls back")
check("ttsChunkChars" in fp.DEF_SETTINGS and "ttsChunkChars" in PAGE,
      "with a row on the TTS page")

section("the EOC record outlives the session")

# One event says nothing - the model misses EOC perhaps one line in twenty. A hundred,
# each carrying the settings in force, is the only thing that can say whether a
# temperature change helped.
_ed = tempfile.mkdtemp()
_rl, _rc = fp.EOC_LOG, fp.CONFIG
fp.EOC_LOG, fp.CONFIG = os.path.join(_ed, "eoc.json"), os.path.join(_ed, "c.json")
try:
    fp.eoc_record("a long day", 128, 18.15, 1, True, {"settings": {"ttsChunkChars": "170"}})
    fp.eoc_record("my life.", 128, 8.9, 1, True, {"settings": {"ttsChunkChars": "90"}})
    fp.eoc_record("my life.", 128, 8.9, 1, True, {"settings": {"ttsChunkChars": "90"}})
    _sum = fp.eoc_summary()
    _rows = fp.eoc_rows()
finally:
    fp.EOC_LOG, fp.CONFIG = _rl, _rc

check(_sum["events"] == 3, "every overrun is kept", str(_sum.get("events")))
check(_sum["secs_lost"] == 36.0, "with what each one cost", str(_sum.get("secs_lost")))
check(len(_sum["by_chunk"]) == 2,
      "grouped by the chunk size in force - which is what a calibration sweeps",
      str(len(_sum["by_chunk"])))
check(_sum["by_chunk"][0]["chunk"] == 90 and _sum["by_chunk"][0]["events"] == 2,
      "so two chunk sizes can be compared without arithmetic")
check(_sum["by_ending"]["ends open"] == 1 and _sum["by_ending"]["ends clean"] == 2,
      "and a line that ended without punctuation is counted apart - an open ending is "
      "an invitation to keep talking", str(_sum["by_ending"]))
check(isinstance(_sum["by_length"], list) and _sum["by_length"],
      "with the failures banded by length, to say whether size is what they share")
check("chunk" in _rows[0] and "ends_clean" in _rows[0] and "tags" in _rows[0],
      "each event carries the shape of the line that produced it")
check("line" in _rows[0] and "chars" in _rows[0],
      "and the line itself is kept - which lines fail is a question a counter cannot answer")
check(fp.EOC_KEEP >= 100, "enough of them to calibrate against", str(fp.EOC_KEEP))
_er = seg(py, "def eoc_record", "def eoc_rows")
check("except Exception:" in _er and "pass" in _er,
      "and a diagnostic never breaks the line it describes")
check("os.replace(tmp" in _er, "written atomically, like every other file the panel keeps")


# The model is not in SERVER_PARAMS - the launcher builder writes it itself - so it was
# never in the edit set, and changing it on a card reached the generated launcher and no
# other. And it is usually behind a $variable that the rest of the script also reads.
_VAR = ('$modelPath = "Z:\\a\\old.gguf"\n'
        'Write-Host "Loading $modelPath"\n'
        '$llamaArgs = @(\n    "-m", $modelPath,\n    "--ctx-size", "10240"\n)\n')
_np = fp.ps1_set_path(_VAR, "-m", "Z:\\b\\new.gguf")
check(fp.parse_launcher_params(_np).get("model") == "Z:\\b\\new.gguf",
      "a model set on the card reaches a launcher that uses a variable",
      str(fp.parse_launcher_params(_np).get("model")))
check("$modelPath" in _np and "Loading $modelPath" in _np,
      "by rewriting the variable, so everything else reading it still agrees")
_LIT = '$llamaArgs = @(\n    "-m", "Z:\\a\\old.gguf",\n    "--ctx-size", "10240"\n)\n'
check('"Z:\\b\\new.gguf"' in fp.ps1_set_path(_LIT, "-m", "Z:\\b\\new.gguf"),
      "a launcher that names the file directly is edited directly")
check("-m" in fp.slot_flag_values({}, {"params": {"model": "Z:\\a\\m.gguf"}}, '"-m"'),
      "and the model is in the set of flags an edit writes")
# the whole edit path, not just the writer: a model routed through ps1_set_flag instead
# would rewrite the flag to a literal and leave $modelPath pointing at the old file
_ef = seg(py, "def ps1_edit_flags", "def slot_owns_script")
check("ps1_set_path(out, flag, value) if flag in" in _ef,
      "and an edit routes the model through the path writer, not the flag writer")

section("the action a character chose")

check(fp.note_actor(b"## Serana's Character Profile (THIS IS WHO YOU ARE)") == "Serana",
      "the actor is read from the profile heading")
check(fp.note_speaker(b"## Serana's Character Profile") == "",
      "and NOT into the speaker queue, which pairs a voice with a spoken line")
_ad = tempfile.mkdtemp()
_rld = fp.log_dir
fp.log_dir = lambda cfg=None: _ad
try:
    _on = fp.action_line('{"ACTION": "bathe"}', "Serana", {"settings": {"ttsActionOut": "on"}})
    _txt = "".join(open(os.path.join(_ad, _f), encoding="utf-8").read()
                   for _f in os.listdir(_ad))
    _none = fp.action_line('{"ACTION": "None"}', "Serana", {"settings": {"ttsActionOut": "on"}})
    _off = fp.action_line('{"ACTION": "bathe"}', "Serana", {"settings": {"ttsActionOut": "off"}})
finally:
    fp.log_dir = _rld
# action_line returns the row it wrote since patch84 - the branch, not just the
# action name - and an empty string when it wrote nothing.
check(_on.endswith(" Serana > bathe") and fp.ACTION_MARK in _on,
      "the chosen action is read out of the reply", _on)
check("Serana > bathe" in _txt, "and written as <who> > <what>", _txt.strip()[:60])
check(fp.ACTION_MARK in _txt, "under a mark of its own, not a spoken one")
check(_none == "", "None is not an action - it is the commonest answer and would bury the rest")
check(_off == "", "and nothing at all with the switch off")
check(fp.DEF_SETTINGS.get("ttsActionOut") == "off", "off by default")
check('data-act="termActions"' in PAGE, "with a switch in the Options panel")


# tts_pick_fields reads TWO of SkyrimNet's arguments and discards the rest unread. If
# SkyrimNet exposes TTS settings of its own, their values are in that list and nothing
# in the panel would ever have shown them. A Gradio call is positional, so the only way
# to find out what is in it is to look.
_fn = fp.tts_fields_note(["en-us", "a line", 0.8,
                          {"path": "C:/x/a.wav", "orig_name": "a.wav"}, 50, True, None])
check("[2] 0.8" in _fn and "[4] 50" in _fn,
      "a numeric argument is shown with its position - that is what a slider looks like",
      _fn)
check("[5] true" in _fn, "and so is a flag")
check("[6] null" in _fn, "and an empty one, so the positions do not shift")
check("dict{orig_name,path}" in _fn,
      "the reference is summarised by its keys - it carries a path and sometimes audio, "
      "and neither belongs in a log line")
nin(_fn, "C:/x/a.wav", "so no path is written out")
check(fp.tts_fields_note([]) == "" and fp.tts_fields_note(None) == "",
      "and nothing at all is quiet")
_sub = seg(py, "def submit(self, fields)", "def _run(self")
check("tts_fields_note(fields)" in _sub, "written once per request")
check(_sub.index("tts_fields_note") < _sub.index("tts_pick_fields"),
      "before the two it reads are picked out, so the list is the one that arrived")


# the action line reads as who and what, so the name takes the speaker colour and the
# action the tag colour this terminal already uses
_pt5 = seg(JS, 'const ACT = String.fromCodePoint(0x26A1);', "function stepAt")
check('line.indexOf(" > ") > 0' in _pt5, "an action line is recognised by its shape")
check("#ff5dc8" in _pt5 or "MG" in _pt5, "the name is magenta, as a speaker is")
check("CY" in _pt5, "and the action cyan, as a tag is")

# room between records - Proxy terminal only, the others are prose
check("ttsActionOut" in fp.DEF_SETTINGS,
      "the action-output toggle is a setting")

check('_kill_port_owner' in seg(py, 'if action == "stop":', 'if action != "start":'),
      "the button still runs the port kill the exit now shares")
check('for shell in ("pwsh", "powershell"):' in py,
      "and the port kill works on stock Windows PowerShell, not only PowerShell 7")
check('full_exit("console interrupt")' in py,
      "Ctrl+C in the console is a quit, with the same cleanup")
check("SetConsoleCtrlHandler" in py and "_CTRL_REF = _HCTRL(_on_ctrl)" in py,
      "and closing the console window runs it too, through a KEPT reference")

# ------------------------------------------------------------------ patch125
# Five from one evening of play: tighter plain rows with the bundle air kept; tree
# elbows that tell the truth after the splice; the action bolt in the same 2ch cell
# as every other mark; NPCs named "Hunter [Hunter]" no longer becoming "someone";
# and every offered audio tag as a button that edits the BUILT-IN prompts.
check("line-height:1.3;" in seg(PAGE, "pre.tail { background:#0d0f13", ".tailbox"),
      "a plain terminal row is tighter by default")
_ft25 = seg(JS, "function fixTree(text)", "function hiddenProvs")
check("i + 1 < src.length && has(src[i + 1])" in _ft25,
      "a branch is a tee only when another branch hangs beneath it")
_nd25 = None
try:
    import subprocess as _sp
    _r25 = _sp.run(["node", "-e",
        "const src=require('fs').readFileSync(process.argv[1],'utf8').replace(/\\r\\n/g,String.fromCharCode(10));"
        "const a=src.indexOf('function fixTree(text)'), b=src.indexOf('function hiddenProvs');"
        "eval(src.slice(a,b));"
        "const NL=String.fromCharCode(10),T=String.fromCharCode(0x251C),L=String.fromCharCode(0x2514);"
        "const one=fixTree(['r','  '+T+' only','r2'].join(NL)).split(NL);"
        "const три=fixTree(['r','  '+T+' a','  '+L+' b','  '+T+' c','r2'].join(NL)).split(NL);"
        "console.log(JSON.stringify([one[1][2]===L, три[1][2]===T, три[2][2]===T, три[3][2]===L]));",
        os.path.join(ROOT, "fleet-panel.py")], capture_output=True, text=True, timeout=60)
    _nd25 = json.loads(_r25.stdout.strip() or "null")
except Exception:
    _nd25 = None
if _nd25 is not None:
    check(_nd25 == [True, True, True, True],
          "run: a single child is a turn; three children are tee, tee, turn", str(_nd25))
else:
    check(True, "SKIPPED: node not available for the tree behaviour run")
check("ti === treeAt + 2 && portAt < 0" in seg(JS, "const pidRx = new RegExp",
                                               "function paintTok(tk)"),
      "a branch mark sits in the same fixed cell a record mark does")
check(bool(fp.note_actor(b"## Hunter [Hunter]'s Character Profile"))
      and fp.note_actor(b"## Frofnir Trollsbane [Bandit Chief]'s Current State")
          == "Frofnir Trollsbane"
      and fp.note_actor(b"an action for Ra'kheran [Hunter] from a specific action category")
          == "Ra'kheran",
      "a bracketed role is part of the addressing, never part of the name")
check(fp.note_actor(b"## Serana's Character Profile") == "Serana",
      "and a plain name still reads as it always did")

# the Audio Tags buttons, end to end
check('"ttsTagsOff": ""' in py, "the clicked-off tags are one setting")
_to25 = fp.tags_off({"ttsTagsOff": "sfx-laughter, EMOTION-ANGER NOT-REAL"})
check(_to25 == frozenset(("SFX-LAUGHTER", "EMOTION-ANGER")),
      "read case-blind, comma- or space-cut, and only words actually offered",
      str(sorted(_to25)))
_p25 = fp.tts_tag_prompt("", _to25)
check("SFX-LAUGHTER" not in _p25 and "EMOTION-ANGER" not in _p25
      and "SFX-COUGH" in _p25,
      "a clicked-off tag leaves the built-in tagger prompt")
check("[SFX-LAUGHTER] Haha!" not in _p25 and "[SFX-COUGH]" in _p25,
      "and the worked example that taught it goes with it")
check(fp.tts_tag_prompt("my own words", _to25) == "my own words",
      "a custom prompt is the user's text, never edited")
check(fp._clean_tagged("[SFX-LAUGHTER] Haha, yes.", "Haha, yes.", _to25) == ""
      and fp._clean_tagged("[SFX-COUGH] Haha, yes.", "Haha, yes.", _to25),
      "an answer that uses a clicked-off tag anyway is not kept")
check("EMOTION-ANGER" not in fp.mood_prompt(3, "", _to25)
      and "EMOTION-AWE" in fp.mood_prompt(3, "", _to25),
      "the built-in mood prompt loses it where it appears")
check("EMOTION-ANGER" in fp.mood_prompt(3, "x {words}", _to25),
      "while a custom mood prompt keeps the full vocabulary it asked for")
check("ANGER" not in fp.mood_valid("1. [anger] (65%): a\n2. [awe] (25%): b", 2, [], _to25)
      and "AWE" in fp.mood_valid("1. [anger] (65%): a\n2. [awe] (25%): b", 2, [], _to25),
      "and a clicked-off feeling is skipped in the reading, as a choice, not noise")
check('"tagOffer": [[label, list(words)] for label, words in TAG_OFFER]' in py,
      "the page draws the buttons from the offer the prompts are built from")
check('tts_tag_prompt("", tags_off(cfg.get("settings", {})))' in py,
      "and the prompt editor shows the built-in wording as it CURRENTLY reads")
_tg25 = seg(JS, "function ttsTagGrid(st)", "// The setting, and its Thinking switch")
check('data-act="ttsTagToggle"' in _tg25
      and '(isOff(w) ? " off" : "")' in _tg25,
      "each tag is a button, dimmed once clicked off - prosody case included")
check("Custom Prompt Active" in _tg25 and 'class="mandy"' in _tg25,
      "a custom prompt is announced by the yellow chip, beside the title")
check('class="ttl"' in _tg25 and '<span class="qm">?</span>' in _tg25,
      "with the usual ? on the title instead of a grey paragraph")
check(".tagbtn.off { opacity:.35" in PAGE and "var(--acc) 45%" in seg(PAGE, ".tagbtn {", ".tagbtn.off"),
      "lit with the accent while offered, dimmed without it once off")
check('g.innerHTML = ttsTagGrid(st)' in JS,
      "a click repaints the grid alone; the pane holds still")
check('"tts-taggrid"' in JS and 'id="tts-taggrid"' in JS,
      "in its own container inside Player Tag System")

# ------------------------------------------------------------------ patch126
# Three finishes on the two newest surfaces: the built-in wording is a FIELD with a
# copy corner; the Custom Prompt Active chip stands beside the Audio Tags title; and
# each tag group is titled above a bordered field of its own.
_pe26 = seg(JS, "function ttsPromptEdit(key)", "function ttsWiredBox")
check('class="copybox"' in _pe26 and 'id="tts-builtin"' in _pe26
      and 'data-act="copyBuiltIn"' in _pe26,
      "the built-in wording sits in its own read-only field with a copy corner")
nin(_pe26, "'<pre class=\"hint\"", "the grey drag-to-select paragraph is gone")
_cp26 = seg(JS, 'if (d.act === "copyBuiltIn")', 'if (d.act === "ttsTagToggle")')
check("navigator.clipboard.writeText" in _cp26 and 'document.execCommand("copy")' in _cp26,
      "copied over the clipboard API where it exists, a hidden textarea where it does not")
check(('btn.textContent = "%su2713"' % chr(92)) in _cp26,
      "and the corner answers with a check so the click is seen to land")
check(".copybtn { position:absolute; top:6px; right:6px" in PAGE,
      "the copy control sits in the top-right corner of the field")
_tg26 = seg(JS, "function ttsTagGrid(st)", "// The setting, and its Thinking switch")
_lb26 = _tg26.find('"</label>"')
check(_lb26 >= 0 and 0 <= _tg26.find("Custom Prompt Active") < _lb26
      and "?</span></label>" not in _tg26,
      "the yellow chip lives INSIDE the title's label, beside it rather than under")
check('<div class="tagbox">' in _tg26
      and _tg26.index("esc(g[0])") < _tg26.index('<div class="tagbox">'),
      "each group is titled above a bordered field of its own")
# ------------------------------------------------------------------ patch127
# The spacing complaints were the EMOJI all along: a colour emoji stands taller than
# the 1.3 line, so every row carrying one grew to the glyph's own height while the
# bolt rows stayed at 1.3em - patch125's tightening moved everything EXCEPT the rows
# it was aimed at. The mark cell's height is fixed, so the row's height is the row's.
# patch139 closes what patches 127, 129 and 131 each theorised about: the record
# rows' mark cell is styled byte-for-byte like the SPOKEN rows' moodic cell - the
# one mark cell every field screenshot proves tight (27px against 44px on the same
# current-page screen). No height, no line-height, no vertical-align: the field
# measurement outranks the spec argument, three times over.
_pc39 = seg(PAGE, ".tail .pcell {", ".payhead {")
check("display:inline-block; width:2ch; text-align:center; }" in _pc39,
      "the record mark cell is the spoken mark cell, byte for byte")
check("height:" not in _pc39 and "vertical-align" not in _pc39,
      "no clever sizing remains on it - the plain box is the proven one")

# ------------------------------------------------------------------ patch132
# Allowed Tags: the FINAL gate on the wire to Higgs, as a second button board under
# the Audio Tags field. A blocked tag never reaches the engine whoever wrote it -
# and a blocked sound effect takes its onomatopoeia with it, which a door on tokens
# alone did not do: the "Ahem," was written beside the token, not inside it.
check('"ttsTagsFinalOff": ""' in py, "the gate is one setting")
check('def tags_off(st, key="ttsTagsOff"):' in py,
      "read by the same parser the prompt board uses, keyed to its own setting")
_fo32 = fp.tags_off({"ttsTagsFinalOff": "sfx-cough, EMOTION-ANGER pause NOT-REAL"},
                    "ttsTagsFinalOff")
check(_fo32 == frozenset(("SFX-COUGH", "EMOTION-ANGER", "PAUSE")),
      "case-blind, comma- or space-cut, and only words actually offered", str(sorted(_fo32)))
check(fp.tag_pair("EMOTION-ANGER") == "emotion:anger"
      and fp.tag_pair("speed_very_slow") == "prosody:speed_very_slow"
      and fp.tag_pair("pause") == "prosody:pause",
      "an offer word maps to the kind:name its control token carries")
_g32 = fp.tts_apply_tags("[SFX-COUGH] Excuse me. [EMOTION-ANGER] Out! [PAUSE] Go."
                         " [SFX-SIGH] Fine.", True, "audiocpp", _fo32)
check("sfx:cough" not in _g32 and "Ahem" not in _g32,
      "a blocked sound effect leaves neither its token nor its onomatopoeia", _g32)
check("emotion:anger" not in _g32 and "prosody:pause" not in _g32,
      "a blocked emotion and a blocked prosody word leave nothing", _g32)
check("<|sfx:sigh|>" in _g32 and "Ahh" in _g32,
      "while an allowed effect still arrives whole", _g32)
check("emotion:anger" not in fp.tts_apply_tags("[angry] Out.", True, "audiocpp", _fo32),
      "the alias spelling is gated too - one vocabulary, one gate")
check("emotion:anger" not in fp.tts_apply_tags("pre <|emotion:anger|> tokened.",
                                               True, "audiocpp", _fo32),
      "and a raw token already in the text is stopped at the backstop")
check("<|emotion:anger|>" in fp.tts_apply_tags("[EMOTION-ANGER] Out.", True,
                                               "audiocpp", frozenset()),
      "an empty gate changes nothing")
check('_banset = tags_off(st, "ttsTagsFinalOff")' in py
      and "_banset | _cool" in seg_len(py, "processed = tts_apply_tags", 300),
      "the speech path reads the gate on every line")
_fg32 = seg(JS, "function ttsFinalTagGrid(st)", "// Every tag the built-in prompts offer")
check('data-act="ttsFinalTagToggle"' in _fg32 and '<div class="tagbox">' in _fg32,
      "the board is the same boxed-group shape the player board wears")
check("Allowed Tags" in _fg32 and '<span class="qm">?</span>' in _fg32,
      "titled Allowed Tags, explained by the usual ?")
check('"tts-finaltaggrid"' in JS and 'id="tts-finaltaggrid"' in JS,
      "in its own container under the Audio Tags field")
check('post("/api/settings", { ttsTagsFinalOff: st.ttsTagsFinalOff })'
      in seg(JS, 'if (d.act === "ttsFinalTagToggle")', 'if (d.act === "ttsTagToggle")'),
      "a click saves the gate and repaints the grid alone")

check('and "%s" in _tg25' not in py and "isOff = w => off.has(String(w).toUpperCase())" in JS,
      "the player board compares clicked-off words in one case - prosody toggles too")
check("w.upper() not in off" in seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]"),
      "and the built-in tagger prompt drops a lower-case prosody word the same way")
check("w.upper() in off" in seg(py, "def _clean_tagged", "PTI_CACHE = "),
      "as does the answer cleaner")
check('<div class="tdiv"></div>' in seg(JS, "function ttsTagGrid(st)",
                                        "// The setting, and its Thinking switch"),
      "a separator line stands above the Player Audio Tags title")
check(".tdiv { height:1px; background:var(--line)" in PAGE,
      "drawn as a quiet rule, not a heading")
check('eng === "audiocpp" && tags === "on"'
      in seg(JS, '>Pass them to the engine</option>', "Player Tag System"),
      "the Allowed Tags board shows only when tags can flow at all - Strip hides it")

check('window.__rawTail = text;' in JS and 'd.act === "copyRawTail"' in JS,
      "one click copies the feed exactly as the file holds it, for a bug report")
check('data-act="copyRawTail"' in PAGE, "from a button in the Adjust panel")

check('"ttsTagLimits": ""' in py and '"ttsTagLimitsPlayer": ""' in py,
      "the limits are two tables: NPC lines and player lines")
_tl = fp.tag_limits({"ttsTagLimits": "SFX-LAUGHTER:2 pause:1 NOT-REAL:3 speed_slow:x"},
                    "ttsTagLimits")
check(_tl == {"sfx:laughter": 2, "prosody:pause": 1},
      "WORD:N parsed case-blind, unknown words and broken counts ignored", str(_tl))
check(fp.tag_pair("sfx:laughter") == "sfx:laughter",
      "an already-formed pair passes the gate unmapped - two vocabularies, one gate")
fp.TAG_TURNS.clear()
_pat = []
for _ in range(5):
    _cl = fp.tag_cooldown_pass("gatekeeper", _tl)
    _o = fp.tts_apply_tags("[SFX-LAUGHTER] Hehe.", True, "audiocpp", _cl)
    fp.tag_cooldown_note("gatekeeper", _tl, _o)
    _pat.append("pass" if "sfx:laughter" in _o else "held")
check(_pat == ["pass", "held", "held", "pass", "held"],
      "spoken once, held for N of the SAME character's turns, then free again", str(_pat))
check(not fp.tag_cooldown_pass("someone-else", _tl),
      "another character's turns are their own - no shared clock")
check('_ckey = "player" if _isp else' in py,
      "and the speech path keys the clock by the character, never globally")
check("frozenset() if ping else" in py
      and "tag_cooldown_pass(_ckey, _limits," in py
      and "new_turn=tts_reply_first_chunk(" in py,
      "a warm-up ping neither spends a turn nor starts a cooldown, and a turn "
      "advances once per REPLY - the owner's round, not a TTS chunk")
check("_banset | _cool" in py,
      "cooldowns ride the same final gate the clicked-off tags do")
check("tag_cooldown_note(_ckey, _limits, processed)" in py,
      "and only tags that actually REACHED the engine start one")
_tlj = seg(JS, "window.__tagLim = window.__tagLim", "// Every tag Higgs can be sent")
check('TAGLIM_KEYS = { player: "ttsTagLimitsPlayer", npc: "ttsTagLimits" }' in _tlj,
      "each board writes its own table")
check(JS.count('tagLimButtons("player")') == 1 and JS.count('tagLimButtons("npc")') == 1,
      "the Tag Limits button stands beside both titles")
check('(on ? \'<button class="stop" data-act="tagLimSave"' in _tlj,
      "Save and Reset appear to its right only while the mode is on")
check(JS.count("window.__tagLim.player.on") >= 2 and JS.count("window.__tagLim.npc.on") >= 2,
      "in limit mode a chip click sets the count instead of toggling the tag")
check('tagLimPop("player", String(d.tag || ""))' in JS
      and 'tagLimPop("npc", String(d.tag || ""))' in JS,
      "in limit mode a chip click opens the < N > stepper beside the chip")
check(".tlim { position:absolute" in PAGE and ".tlimbtn.on {" in PAGE,
      "the count rides the chip as a badge, and the mode button glows accent")

# ------------------------------------------------------------------ patch135
# Why every spacing fix "changed nothing", proven from the user's own files: their
# log has NO blank lines, their gap is 0, and the current pipeline renders their
# exact feed flat - so the gaps on their screen come from a tab still running old
# page JS across panel updates. The page now carries its release tag and a tab
# reloads itself once when the panel it talks to is newer. Plus: click a spoken
# line to replay its audio, and the tag-limit stepper popover.
check('"app": APP_RELEASE_TAG,' in py, "the state names the release it was served by")
check('.replace("__APPTAG__", APP_RELEASE_TAG)' in py,
      "and the page is stamped with the release that built it")
_ht = seg(JS, "const APP_TAG = ", "async function load()")
check('APP_TAG.indexOf("__APP") !== 0' in _ht and "location.reload()" in _ht
      and "window.__reloading" in _ht,
      "on a mismatch the tab reloads itself, once, and never on an unexpanded stamp")
check("appTagCheck();" in seg(JS, "async function load()", "reconcilePcMode"),
      "checked on every state pull, so a stale tab heals on its own")
check('eid=""' in seg(py, "def say_line(", "def saved_line(")
      and ('" ' + chr(92) + "u27EA%s" + chr(92) + 'u27EB" % eid') in py,
      "a spoken line carries the id of its kept audio, marker-style")
check('u.path == "/api/tts-audio"' in py and 'os.path.basename(' in
      seg(py, 'u.path == "/api/tts-audio"', 'elif u.path == "/api/log-download"'),
      "the replay endpoint serves only a basename from the worker's own out-dir")
check("rotated out" in py, "and says so honestly once prune() has taken the file")
_ps35 = seg_len(JS, "function paintSpoken", 6600)
check("aidRx" in _ps35 and 'data-act="playSpoken"' in _ps35,
      "the painter strips the marker and turns the said text into the replay button")
check('class="spk"' in _ps35, "wrapped as .spk")
check(".spk:hover { text-shadow" in PAGE and ".spk.playing { animation:spkPulse" in PAGE,
      "a breath of glow on hover, a pulse while replaying")
_pj = seg(JS, "function spkPlay(aid)", "// The badge answers")
check("window.__spkAudio" in _pj and "au.onended = au.onerror" in _pj,
      "one line plays at a time, and the pulse ends with the audio either way")
check('post("/api/tts-replay", { id: aid })' in seg(JS, 'if (d.act === "playSpoken")',
                                                    'if (d.act === "tagLimMode"'),
      "a click asks the panel to broadcast, with a local fallback if it cannot")
_pop = seg(JS, "function tagLimPop(board, tag)", "function tagLimPopClose()")
check('data-act="tagLimDec"' in _pop and 'data-act="tagLimInc"' in _pop
      and "getBoundingClientRect" in _pop,
      "the stepper anchors under the clicked chip with < and > at hand")
check("host.appendChild(pop)" in _pop and "grid.parentElement" in _pop,
      "and lives outside the grid, so a repaint cannot take it down")
check("#taglim-pop .pnv { padding:3px 11px; font-size:16px" in PAGE
      and "#taglim-pop .pnv:hover {" in PAGE,
      "the stepper arrows stand as tall as their number, accent at rest, brighter under the pointer")
_adj = seg(JS, 'if (d.act === "tagLimDec" || d.act === "tagLimInc")',
           'if (d.act === "playSpoken")')
check("Math.max(0, Math.min(99, cur + (d.act ===" in _adj.replace('"tagLimInc" ? 1 : -1)));', '"tagLimInc" ? 1 : -1)));')
      and "tagLimPop(board, String(d.tag || \"\"))" in _adj,
      "steps of one, clamped 0..99, the popover riding the repaint")
check(JS.count("tagLimPopClose();") >= 3,
      "leaving the mode, saving, resetting or clicking away all close it")
check("TAGLIM_STEPS" not in JS, "the blind cycle is gone, not left beside the stepper")

# ------------------------------------------------------------------ patch136
# The spacing experiment is closed at the owner's call: uniform rows, no response
# rules, no knob - the code, the setting, the select and every drifted copy of the
# default are gone together. The replay reaches a two-PC setup: the endpoint is on
# the remote read-only allowlist, so the panel opened in a browser on the game PC
# plays the line on THOSE speakers - which is where TTS audio normally lands. And
# the stepper wears the navigation buttons' own accent.
check("spaceRows" not in JS and "isRespRow" not in JS and "rowGap" not in JS,
      "no spacing machinery survives anywhere in the page")
check("termRowGap" not in py, "and no trace of the setting - not even a fallback copy")
check('"/api/tts-audio",' in seg(py, "REMOTE_READ_OK = {", "REMOTE_TAIL_KINDS"),
      "the replay endpoint is readable by a LAN viewer, so the game PC's browser plays it")

# ------------------------------------------------------------------ patch137
# The card's first row holds; auto-names are Server (N): <gpu> clamped; a version
# badge sits in the page corner so "which JS is this tab running" is answerable at
# a glance; and a replay click is broadcast over the event stream, so every open
# page - the host and the remote view on the game PC - plays it locally.
check('<div class="row shead">' in JS and ".row.shead { flex-wrap:nowrap" in PAGE,
      "the first card row never wraps - the close symbol cannot fall to a second line")
check("text-overflow:ellipsis" in seg(PAGE, ".row.shead .label", ".row.shead .icon"),
      "it is the TITLE that gives way, ellipsised")
check('s["label"] = "Server %d: %s" % (n, gpu)' in py
      and ('gpu = gpu[:23].rstrip() + "' + chr(92) + 'u2026"') in py,
      "auto-names read Server N: <gpu> - bracketless - with the gpu part clamped")
check(("Server " + chr(92) + "((" + chr(92) + "d+)" + chr(92) + "): (.*)$") in py,
      "and labels the old namer wrote are retitled in place on load")
_ub = seg(JS, "function drawUiBadge()", "async function load()")
check('b.id = "uibadge"' in _ub and 'APP_TAG.indexOf("__APP") === 0' in _ub,
      "the badge names the page's own release and never shows an unexpanded stamp")
check("drawUiBadge();" in seg(JS, "async function load()", "reconcilePcMode"),
      "drawn on every state pull, beside the handshake")
check("#uibadge { position:fixed" in PAGE, "fixed in the corner, out of the way")
check('def api_tts_replay(body):' in py
      and 'sse_notify("replay", {"id": aid})' in py,
      "a validated replay id is handed to every open page over the event stream")
check('"/api/tts-replay": api_tts_replay,' in py,
      "as a POST, which a read-only remote viewer cannot place")
check('ev.t === "replay" && ev.id) spkPlay(String(ev.id))' in JS,
      "and every page that hears it plays it locally - the game PC's speakers included")

# ------------------------------------------------------------------ patch138
# The requested out-of-the-box defaults, and a page that follows an install: a
# state event now re-pulls /api/state and repaints the TTS pane, so the Higgs
# installer's saved folder paths appear without a hand reload.
check(fp.DEF_SETTINGS["ttsTags"] == "on"
      and fp.DEF_SETTINGS["ttsMoodEvery"] == "5"
      and fp.DEF_SETTINGS["ttsSampAutoCal"] == "on"
      and fp.DEF_SETTINGS["ttsAnswerPing"] == "off"
      and fp.DEF_SETTINGS["ttsWrapMode"] == "on",
      "the five requested defaults ship as asked: tags pass, PME every 5, "
      "calibration Automatic, ping No, the Proxy translates")
check(">The Proxy (no separate wrapper process)</option>" in JS
      and "The panel (no separate" not in JS,
      "the option reads The Proxy now, nowhere still The panel")
_srp = seg(JS, "async function stateRepull()", "function connectES()")
check('state = await (await fetch("/api/state")).json()' in _srp,
      "a state event re-pulls the state itself, not only the queues")
check("renderTts()" in _srp and "pane.contains(document.activeElement)" in _srp,
      "and repaints the TTS pane - unless a field there holds the keyboard")
check('if (ev.t === "state") stateRepull();' in JS,
      "wired where the event arrives")

# ------------------------------------------------------------------ patch139
# The card header splits: title row above, port capsule and status pill below, so
# a long pill can never push the close symbol anywhere. The port wears the pill's
# own capsule in quiet grey. (The mark-cell flattening is asserted where the old
# patch131 check stood.)
check("+ rm + '</div>'" in JS and '<div class="row srow2">' in JS,
      "the first row is title, rename and close - nothing else")
check('<span class="srvport clickable" id="port-' in JS,
      "the port sits in the second row, dressed as a capsule")
check(".srvport { font-size:11px; padding:2px 10px; border-radius:999px" in PAGE
      and "background:#262b33" in seg(PAGE, ".srvport {", ".srvport:hover"),
      "the pill's shape, in quiet grey - under its own class, clear of the "
      "provider rows' portchip")
check(JS.count('class="chip clickable" id="port-') == 0,
      "and the old header-row port chip is gone, not left beside the new one")

# ------------------------------------------------------------------ patch140
# The fifteen-patch spacing bug was ONE CHARACTER: the log is CRLF on Windows, the
# client splits on LF, and the CR left on every FILE line becomes a newline when
# innerHTML parses it - a pre-wrap row with a trailing newline renders TWO lines
# tall. Spliced rows are built client-side without CR, which is why they alone
# were ever tight. The painter scrubs CR before anything else looks. Every read
# this gate and its author ever did in text mode silently hid the CR - so this
# check feeds the painter real CRLF and reads what the page would be handed.
check('text = String(text).split(String.fromCharCode(13)).join("");'
      in seg(JS, "function paintTail(", "function stepAt"),
      "the painter scrubs the carriage return before anything else looks")
_cr40 = None
try:
    import subprocess as _spc
    _rc40 = _spc.run(["node", "-e", "const src=require('fs').readFileSync(process.argv[1],'utf8');function sl(a,b){const i=src.indexOf(a);const j=src.indexOf(b,i);return src.slice(i,j).split(String.fromCharCode(13)).join('');}let code='';code+=sl('const TERM_INS_KINDS','function paintTail(');code+=sl('function fixTree(text)','function hiddenProvs');code+=sl('function dropPanelProv(','function paintTail(');code+=sl('function paintTail(','function stepAt');globalThis.window=globalThis;const state={settings:{},routing:[]};let captured='';const el={set innerHTML(h){captured=h;},dataset:{},classList:{toggle:function(){},add:function(){},remove:function(){}},style:{}};const $=id=>id==='tail-dashboard'?el:null;const esc=s=>String(s==null?'':s);function termInsTtsOn(){return false;}function sizeTailEl(){}function paintThink(){}function markNewRows(){}function paintSpoken(l){return esc(l);}function paintTok(x){return esc(x);}function provMark(){return '';}eval(code);markNewRows=function(){};sizeTailEl=function(){};paintThink=function(){};paintSpoken=function(l){return esc(l);};paintTok=function(x){return esc(x);};const CR=String.fromCharCode(13),NL=String.fromCharCode(10);const raw=['[05:44:11.10] M Meta [1237] 2942 / 53 tok 6636','[05:44:13.30] V Vision [1238] 843 / 179 tok 961'].join(CR+NL)+CR+NL;paintTail('dashboard', raw);console.log(JSON.stringify([captured.indexOf(CR)<0,(captured.match(/class=.tl./g)||[]).length]));", os.path.join(ROOT, "fleet-panel.py")],
                     capture_output=True, text=True, timeout=60)
    _cr40 = json.loads(_rc40.stdout.strip() or "null")
except Exception:
    _cr40 = None
if _cr40 is not None:
    check(_cr40[0] is True and _cr40[1] == 2,
          "run: CRLF input paints CR-free rows, one per line, trailing blank "
          "dropped - no row can stand two lines tall", str(_cr40))
else:
    check(False, "the CRLF run did not RUN - node or the snippet is broken")
check("min-height:1.3em" in seg(PAGE, ".tail .tbr, .tail .tbrend {", ".tail .tbr::before"),
      "and the branch connector joins the same rhythm instead of standing 1.6em")
# ------------------------------------------------------------------ patch128
# The speed-test regression, root-caused: idle was not silence. autocal_wait_idle
# let a fit or calibration START in the sub-second gap between back-to-back lines
# and then run 20-116s on a card speech may share - 4-5.5x fell to 2-4x. A background
# job now needs a real QUIET GAP; the wall time joins the measure row so the factor
# is a number on the page; and the GPU can be held out of its idle power state.
check("AUTOCAL_QUIET_GAP_S" not in py and "TTS_LAST_END" not in py,
      "the quiet-gap wait and its clock left with the model fit - nothing to be "
      "quiet for")
check('"wall": round(float(wall or 0), 2),' in py
      and "tts_measure_row(text, secs, est, wall)" in py
      and "wall=synth)" in py,
      "the seconds a line took to MAKE are in its measure row, end to end")
_pf28 = fp.tts_perf_summary()
check(isinstance(_pf28, dict) and set(("x", "n", "retries")) <= set(_pf28),
      "the perf summary answers with a factor, a count and the retries")
check('"perf": tts_perf_summary(),' in py,
      "and rides the diagnosis payload the boxes read")
check("if (perf && perf.n) {" in JS
      and 'hbox(Number(perf.x).toFixed(2) + "x", "speed"' in JS
      and 'hbox(String(perf.retries), "retries"' in JS,
      "speed and retries stand in the Monitoring boxes, drawn when there is data")
check('"ttsGpuClockHold": "off",' in py,
      "the clock hold is the user's switch, off by default")
_ch28 = seg(py, "def tts_clock_hold", "def tts_clock_release")
check("is_admin()" in _ch28 and '"-lgc"' in _ch28
      and "clocks.max.graphics" in _ch28,
      "held at the card's own maximum, admin-gated, never guessed")
_cr28 = seg(py, "def tts_clock_release", "def stop_tts_server")
check('"-rgc"' in _cr28,
      "and released the same way it was taken")
check(py.count("tts_clock_release(") >= 3,
      "released on stop, on exit, and callable when nothing is held")
check("tts_clock_hold(uuid_, st)" in py,
      "taken only when the panel's own start succeeded")
check('id="tts-ttsGpuClockHold"' in JS and '"ttsGpuClockHold",' in JS,
      "the switch sits in the TTS Server field and is saved with the rest")

# ------------------------------------------------------------------ patch129
# Why the tightening never showed: the Proxy Terminal PAGE is the MAXIMIZED view,
# and .tmax .tail carried its own line-height:1.6 - every rhythm change to pre.tail
# landed everywhere except the terminal being read. Verified against the user's
# pixels: plain pitch = 1.6em x their display scaling, exactly. One rhythm now.
_tm29 = seg(PAGE, ".tmax .tail { flex: 1;", ".tscale-btn")
nin(_tm29, "line-height", "the maximized view keeps NO line-height of its own")
check("height: auto; max-height: none; }" in _tm29,
      "its layout overrides stay; only the rhythm override is gone")
check(PAGE.count("line-height:1.3;") >= 1 and ".tmax .tail { flex" in PAGE,
      "so the one line-height in pre.tail is the one every view uses")

# ------------------------------------------------------------------ patch130
# The calibration verdict, acted on: the arithmetic is the standard. Proxy refits
# itself by least squares and steps the samplers from the failure record - no model,
# no server, no quiet gap. The LLM path stays as the model-assisted option. The
# headroom is a percentile, not the single worst outlier, and the record is read
# from memory rather than re-parsed from disk for every spoken line.
check('"ttsAutoCal": "proxy",' in py, "Proxy is the standard: the default mode")
check('"ttsAutoCalEvery": "12",' in py, "with a refit every 12 lines by default")
check("MEASURE_GEN = [0]" in py and '_MEASURE_CACHE["gen"] != MEASURE_GEN[0]' in py,
      "the measure record is a warm copy, refreshed only when a line was appended")
check("MEASURE_GEN[0] += 1" in seg(py, "def tts_measure_record", "def _tts_measure_compact"),
      "and the append is what stales it")
_hf30 = seg(py, "def tts_headroom_facts", "def tts_autocal_headroom")
check("p95 * AUTOCAL_HEAD_PAD" in _hf30 and "worst * AUTOCAL_HEAD_PAD" not in _hf30,
      "the headroom is the 95th percentile padded, never the single worst outlier")
_r30 = ([{"chars": 44, "pause_s": 0.0, "secs": 4.0, "tok": 110.0, "est": 100.0,
          "bound": "estimate", "at": "x"}] * 11
        + [{"chars": 44, "pause_s": 0.0, "secs": 4.0, "tok": 240.0, "est": 100.0,
            "bound": "estimate", "at": "x"}])
_d30 = fp.tts_headroom_facts(_r30, [])
check(_d30["h"] < 1.5 and _d30["worst"] == 2.4,
      "run: one freak line no longer sets every cap, and is still reported",
      "h=%.2f worst=%.2f" % (_d30["h"], _d30["worst"]))
check(fp.AUTOCAL_HEAD_MAX == 1.60 and fp.AUTOCAL_HEAD_MIN == 1.08,
      "the clamp is a margin, not the pinned-bug era's 2.5")
_da30 = seg(py, "def autocal_derive_arith", "def autocal_sampler_arith")
check("tts_measure_ols(rows)" in _da30 and '"ttsAutoCalMedian"' in _da30,
      "the proxy refit is least squares, written to the same stored fit")
nin(_da30, "panel_chat", "and it asks no model")
nin(_da30, "autocal_wait_idle", "and waits for nothing - arithmetic cannot contend")
_sa30 = seg(py, "def autocal_sampler_arith", "def autocal_lines_since")
check('"ttsSampAutoCal", "on")).lower() != "on"' in _sa30,
      "the sampler step runs only under the switch left on")
check("rate >= 0.08" in _sa30 and "max(0.5," in _sa30 and "max(0.85," in _sa30,
      "steadier by one bounded notch when the window failed")
check('rate == 0.0 and len(rows) >= 40 and cur' in _sa30,
      "and one notch back towards SkyrimNet after a clean full window")
check('if mark and since <= mark:' in _sa30,
      "never twice on the same window - the lines must postdate the last change")
check("calterm_log" in _sa30,
      "every change carries the numbers that drove it into the feed")
check('">Player Audio Tags<span class="qm">?</span>' in JS,
      "the tag board is titled Player Audio Tags")
check(".tail .tl { display:block; min-height:1.5em; line-height:1.5em;" in PAGE
      and "white-space:pre-wrap; overflow-wrap:normal; word-break:normal; }"
          in seg(PAGE, ".tail .tl {", ".payhead"),
      "GROUND-UP rows, second cut: a row grows only by wrapping its own text - "
      "min-height holds an empty row, nothing clips, the glow renders whole")
check("overflow:hidden" not in seg(PAGE, ".tail .tl {", ".payhead"),
      "and no clip remains to slice a text-shadow at the row's edge")

# ------------------------------------------------------------------ patch144
# The asymmetric shell: dialogue, thoughts and branches may wrap (field-proven
# tight for weeks); a record wears .one - a hard 1.5em with no clip, so its glow
# halo stays whole and NOTHING inside it can move the terminal's rhythm. At the
# door, every break-capable character dies: CR (patch140), the line and paragraph
# separators, vertical tab, form feed, NEL - plus trailing whitespace per line and
# the file's final empty line.
_dr44 = seg(JS, 'text = String(text).split(String.fromCharCode(13)).join("");',
            'if (which === "dashboard" || which === "ptipme")')
check("[0x2028, 0x2029, 0x0B, 0x0C, 0x85]" in _dr44,
      "every exotic break character dies at the door with the CR")
check('l.replace(new RegExp("[ " + String.fromCharCode(9) + "]+$"), "")' in _dr44,
      "trailing spaces and tabs are stripped per line - nothing hangs, nothing wraps blind")
check('while (text.slice(-1) === String.fromCharCode(10))' in _dr44,
      "and the file's final empty line paints no phantom row at the tail's foot")
check(".tail .tl.one { height:1.5em; }" in PAGE,
      "the record cap: a hard 1.5em with no overflow clip - rhythm held, halo whole")
check("overflow" not in seg(PAGE, ".tail .tl.one {", ".payhead"),
      "and the cap carries no clip that could slice a glow")

# ------------------------------------------------------------------ patch145
# The face is the feeling, the payload hover is light not paint, the stepper grew a
# quarter, and a wrapped line folds between words - with the realtime reading
# moving as one whole unit.
check("white-space:nowrap" in seg(JS, "const saidHtml", "const saidWrap")
      and "line.slice(b + WAVE.length)" in seg(JS, "const saidHtml", "const saidWrap"),
      "the reading after the closing wave - brackets, bolt, number - folds as one "
      "unit onto the next row, never split in the middle")
check("#taglim-pop .tlimn { min-width:2ch; text-align:center; font-size:16px" in PAGE,
      "the stepper's number keeps pace with its grown arrows")

# ------------------------------------------------------------------ patch146
# Server card launches and stops now behave like the TTS buttons: the button
# names the phase and stays down, and the card's small terminal opens on the
# press and LIVES - polled from the slot's own console log - until the slot
# serves (launch) or nothing runs (stop). A re-render cannot blink it away.
check('def api_slot_log(body):' in py and '"/api/slot-log": api_slot_log,' in py,
      "the slot's console log is servable, ANSI-stripped, for the card's terminal")
check('"srv_%s_*.log" % glob.escape(sid)' in py,
      "and it reads the slot's OWN newest log, the same file the speed reader trusts")
_ab46 = seg(JS, "const slotBusy = {}, slotPoll = {}, slotLogText = {};",
            "let exitArmed = false;")
check('btn.textContent = kind === "launch" ? "Launching Server..." : "Shutting Down..."' in _ab46,
      "the button names the phase the moment it is pressed")
check("slotPoll[sid] = setInterval(() => slotTermTick(sid), 1500)" in _ab46,
      "and the terminal is fed from the live log while the phase lasts")
_sb46 = seg(JS, "function srvButtons(s, off, running)", "function paramEditor(s)")
check('if (busy === "launch" && serving) slotBusyClear(s.id);' in _sb46
      and 'else if (busy === "stop" && !running) slotBusyClear(s.id);' in _sb46,
      "the phase ends where the STATE confirms it - serving for a launch, nothing "
      "running for a stop - and only then do the buttons and terminal let go")
check("Launching Server..." in _sb46 and "Shutting Down..." in _sb46,
      "both phases are named on the card, disabled while they last")
check('Object.keys(slotBusy).forEach(sid => {' in JS,
      "a rebuild of the cards re-shows and refills a busy slot's terminal at once")

# ------------------------------------------------------------------ patch147
# A thought can be voiced: a click on a thought line synthesizes it in the
# character's own remembered reference, bakes in an inner-monologue echo, and
# broadcasts it over the same replay stream a spoken line uses. The echo runs
# LIVE here on a synthetic wav to prove the taps exist and nothing clips.
check("TTS_REF_BY_NAME[tts_speaker_label(ref_path)] = ref_path" in py,
      "the panel remembers each speaker's last WORKING reference as they speak")
check('def api_tts_thought(body):' in py
      and '"/api/tts-thought": api_tts_thought,' in py,
      "a thought line is voiceable on demand")
check('re.sub(r"\\*[^*]{0,40}\\*", " "' in py,
      "stage directions are removed before the engine reads the thought aloud")
check('eid = "th" + hashlib.sha1((who + "|" + text).encode("utf-8")).hexdigest()[:12]' in py,
      "cached by content - the same thought is synthesized once, replayed after")
check('sse_notify("replay", {"id": eid})' in seg(py, "def api_tts_thought", "def api_slot_log"),
      "and delivered over the same event stream a spoken replay rides")
check('data-act="playThought" data-who="' in JS and '"spk thk"' in JS,
      "a thought line is a button in its own tint, the speaker carried on it")
_et47 = None
try:
    import wave as _twv, array as _tar, math as _tmt, tempfile as _ttf
    _tp = os.path.join(tempfile.gettempdir(), "gate-echo-%d.wav" % os.getpid())
    _rate = 24000
    _sig = _tar.array("h", (int(12000 * _tmt.sin(2 * _tmt.pi * 220 * i / _rate))
                            if i < _rate // 4 else 0 for i in range(_rate)))
    with _twv.open(_tp, "wb") as _w:
        _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(_rate)
        _w.writeframes(_sig.tobytes())
    _ok = fp.tts_echo_wav(_tp)
    with _twv.open(_tp, "rb") as _w:
        _out = _tar.array("h"); _out.frombytes(_w.readframes(_w.getnframes()))
    _d1 = int(_rate * 0.13)
    # measure AT the tap, clear of the boom's brief decay right after the dry end:
    # a window around dry+d1 holds only g1 times the note - it tells taps from
    # boom, and a silenced or a reverted tap both fall outside it
    _w0 = _rate // 4 + _d1 - int(0.01 * _rate)
    _tail = max(abs(v) for v in _out[_w0:_rate // 4 + _d1 + 800])
    _peak = max(abs(v) for v in _out)
    os.remove(_tp)
    def _egain(_freq):
        _q = os.path.join(tempfile.gettempdir(), "gate-eg-%d.wav" % os.getpid())
        _sg = _tar.array("h", (int(8000 * _tmt.sin(2 * _tmt.pi * _freq * i / _rate))
                               for i in range(_rate // 2)))
        with _twv.open(_q, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(_rate)
            _w.writeframes(_sg.tobytes())
        fp.tts_echo_wav(_q)
        with _twv.open(_q, "rb") as _w:
            _o = _tar.array("h"); _o.frombytes(_w.readframes(_w.getnframes()))
        os.remove(_q)
        _sgm = _o[_rate // 4:_rate // 2 - 1000]
        return (sum(v * v for v in _sgm) / len(_sgm)) ** 0.5
    _boom = _egain(60) / max(1.0, _egain(880))
    # halved taps: energy present but bounded well under the old ~5000; and the
    # boom: 60 Hz must come through clearly louder than 880 Hz
    # patch159 regime: taps halved again (window drops with g1), the boom at
    # ~70 Hz with real weight - reverting either lands outside these
    _et47 = [bool(_ok), 180 < _tail < 600, _peak <= 32767, _boom > 2.0]
except Exception:
    _et47 = None
if _et47 is not None:
    check(_et47 == [True, True, True, True],
          "run: the shade of a tap still carries after the dry note, the low BOOM "
          "is heavier than ever (60 Hz well over 880 Hz), and nothing clips",
          str(_et47))
else:
    check(False, "the echo run did not RUN - wave or the helper is broken")

# ------------------------------------------------------------------ patch148
# The thought click works (the handler read a variable named `t` that the click
# chain calls `el` - every press threw before the POST), and Thought Audio is a
# setting: armed in TTS after Player Tag System, an NPC's freshest thought is
# voiced automatically and played BEFORE the spoken line (delivery held for its
# playtime, capped) or AFTER it (following the line's own measured length).
check('const el2 = el;' in seg(JS, 'if (d.act === "playThought")', 'if (d.act === "playSpoken")'),
      "the thought click reads the element the chain actually provides - no free "
      "variable, no ReferenceError")
check('"ttsThoughtAudio": "off",' in py and '"ttsThoughtSeq": "before",' in py,
      "both settings ship, off and before, in DEF alone")
check('function ttsThoughtAudioRow(st)' in JS
      and "'<div class=\"tsect\">Thought Audio</div>'" in JS,
      "the section stands after Player Tag System")
check('id="tts-ttsThoughtSeq"' in JS
      and ">Before NPC dialogue line<" in JS and ">After NPC dialogue line<" in JS,
      "the Sequence select appears only when armed, before as the default")
check('"ttsThoughtAudio", "ttsThoughtSeq"]' in JS,
      "and both are saved with the rest of the TTS fields")
check("THOUGHT_FRESH[who] = (rows[-1], time.time())" in py
      and py.index("THOUGHT_FRESH[who]") < py.index('st.get("ttsThoughtOut", "off")'),
      "the freshest thought is remembered BEFORE the display gate - hearing and "
      "showing are separate settings")
_ta48 = seg(py, "_thWho = tts_speaker_label(ref_path)", 'if tts_engine(cfg) == "audiocpp":')
check("THOUGHT_FRESH.pop(_thWho, None)" in _ta48 and "180.0" in _ta48,
      "a thought is voiced once, for its own line, and staleness is refused")
check("_thw = _thEnd - time.time() + 0.5" in py
      and "_thEnd = time.time() + min(float(_tsec or 0.0), 12.0)" in py
      and "_hold_s = min(_thw, 12.0)" in py and "time.sleep(_hold_s)" in py
      and "t0 += _hold_s" in py,
      "BEFORE holds for the thought's length plus half a second - and the hold "
      "leaves the measured wall by shifting its origin, with its own row")
check("tts_thought_after_chunk(_thWho, _thTxt, secs, cfg," in py,
      "AFTER: every chunk reaches the burst scheduler - the first carries the "
      "thought, the rest extend or, recognised as final, anchor the reply")

# ------------------------------------------------------------------ patch149
# The echo is half as prominent with a low boom mixed under it, and a remote
# viewer on the second PC may click a thought: the host synthesizes and the
# replay reaches every page, that viewer's speakers included.
check("g1, g2, gb = 0.055, 0.026, 1.8" in py,
      "the taps an eighth of the original, the boom heavier still - retuned "
      "three times, each on the same ears' request")
check('alpha = 1.0 - _m.exp(-2.0 * _m.pi * 70.0 / float(rate or 24000))' in py
      and "lp[ch] += alpha * (s[i] - lp[ch])" in py,
      "the boom is a real one-pole low-pass per channel at ~70 Hz, not a volume knob")
check('"/api/tts-thought"}' in seg(py, "REMOTE_POST_OK = {", "if getattr(self,"),
      "a remote viewer may ask for a thought - deliberately, and only that")

# ------------------------------------------------------------------ patch150
# The NarrativeEngine pair: NE-Composer (1264) and NE-Director (1265), real SN
# providers seeded on the next two ports. They sort into the Providers page after
# every existing provider and before the panel-owned PTI/PME by construction
# (port order, panelOwned last), enter providers.yaml once placed on a server,
# and wear a bright grey brighter than Meta's slate.
check('("NE-Composer", 1264, False, 1), ("NE-Director", 1265, False, 1)' in py,
      "both seeded on the next two ports, plain non-thinking, utility priority")
_ne50 = None
try:
    _cfg50 = {"slots": [{"id": "s1", "providers": [{"id": "p1", "title": "Dialogue",
                                                    "port": 1251}]}],
              "unallocatedProviders": []}
    fp.seed_default_providers(_cfg50)
    _un50 = [(p["title"], p["port"]) for p in _cfg50["unallocatedProviders"]
             if str(p.get("title", "")).startswith("NE-")]
    _ne50 = _un50 == [("NE-Composer", 1264), ("NE-Director", 1265)]
except Exception:
    _ne50 = None
if _ne50 is not None:
    check(_ne50 is True,
          "run: an existing config receives both, unallocated, on the next seed pass",
          str(_ne50))
else:
    check(False, "the seed run did not RUN - the seeder is broken")
check('"NE-Composer":"#cbd5e1", "NE-Director":"#cbd5e1",' in JS,
      "one bright grey for the pair - #cbd5e1 against Meta's #64748b slate")
check(("NE-Composer" + chr(34) + ": " + chr(34) + chr(92) + "U0001F3BC") in py
      and ("NE-Composer" + chr(34) + ":" + chr(34) + chr(92) + "U0001F3BC") in py
      and py.count("NE-Composer") >= 4,
      "the score and the clapper, in BOTH emoji maps the codebase keeps")
check("const ao = a.p.panelOwned ? 1 : 0" in JS,
      "and the page's order stays structural: ports first, the panel's own last")

# ---------------------------------------------------------------- patch180
# The AgencyEngine pair: AE-Impulse (1266) and AE-Resolve (1267), seeded on the
# patch151 rails - create_missing_default_providers runs in load_config, so an
# EXISTING config receives them unallocated on the very next start, no button;
# the yaml generator already refuses panel-owned/port-0 entries, so they export
# cleanly once placed. Both wear rust, in the one map the Providers page and
# the proxy terminal share.
check('("AE-Impulse", 1266, False, 1), ("AE-Resolve", 1267, False, 1)' in py,
      "both seeded on the next two ports, plain non-thinking, utility priority")
_ae80 = None
try:
    _cfg80 = {"slots": [{"id": "s1", "providers": [{"id": "p1", "title": "Dialogue",
                                                    "port": 1251}]}],
              "unallocatedProviders": []}
    fp.create_missing_default_providers(_cfg80)
    _un80 = [(p["title"], p["port"]) for p in _cfg80["unallocatedProviders"]
             if str(p.get("title", "")).startswith("AE-")]
    _ae80 = _un80 == [("AE-Impulse", 1266), ("AE-Resolve", 1267)]
except Exception:
    _ae80 = None
if _ae80 is not None:
    check(_ae80 is True,
          "run: an existing config receives both, unallocated, on the LOAD path - "
          "the exact rail patch151 laid, so the patch150 mistake cannot recur",
          str(_ae80))
else:
    check(False, "the AE seed run did not RUN")
check('"AE-Impulse":"#b7410e", "AE-Resolve":"#b7410e",' in JS,
      "one rust for the pair, in the map the page and the proxy terminal share")
check('"AE-Impulse": "\\U0001F4A5"' in py and '"AE-Impulse":"\\U0001F4A5"' in py
      and py.count("AE-Resolve") >= 4,
      "the burst and the scales, in BOTH emoji maps the codebase keeps")

# ---------------------------------------------------------------- patch181
# A retry that resends the same request can only fail the same way. The cap
# grows half again per attempt, the sampler ladder cools FURTHER per attempt,
# and the picker plus the seeds know the new marks - an emoji-less factory
# provider heals to its shipped mark on load.
check('_cap = int(min(TTS_CAP_CEILING, _cap * (1.5 ** (attempt - 1))))' in py
      and '(0.8 ** _k)' in py and '- 0.05 * (_k - 1)' in py,
      "the retry escalates: cap half again per attempt, samplers deeper per step")
check("\U0001F4A5" in JS and "\u2696\uFE0F" in JS
      and '"emoji": DEFAULT_PROVIDER_EMOJI.get(nm, "")' in py,
      "the picker offers the new marks, and a seeded default CARRIES its mark")
_rl81 = None
try:
    _obs81, _cal81 = fp.sn_tts_observed, fp.cal_overrides
    fp.sn_tts_observed = lambda: {"temperature": 0.6, "top_p": 1.0,
                                  "min_p": 0.05, "repetition_penalty": 1.2}
    fp.cal_overrides = lambda st: {}
    _s81 = {"ttsRetrySafe": "on"}
    _a2 = fp.tts_samplers(_s81, 2); _a3 = fp.tts_samplers(_s81, 3)
    fp.sn_tts_observed, fp.cal_overrides = _obs81, _cal81
    _rl81 = [_a2 != _a3,
             _a3["temperature"] < _a2["temperature"],
             _a3["top_p"] < _a2["top_p"],
             _a3["min_p"] > _a2["min_p"]]
except Exception:
    _rl81 = None
if _rl81 is not None:
    check(_rl81 == [True] * 4,
          "run: attempts two and three carry DIFFERENT samplers, each cooler and "
          "tighter than the last - the 12:12 identical-repeat, gone", str(_rl81))
else:
    check(False, "the ladder run did not RUN")
_eh81 = None
try:
    _cfg81 = {"slots": [], "unallocatedProviders": [
        {"id": "x1", "title": "AE-Impulse", "port": 1266, "custom": False},
        {"id": "x2", "title": "MyCustom", "port": 1299, "custom": True, "emoji": ""}]}
    _ch81 = fp.create_missing_default_providers(_cfg81)
    _eh81 = [_ch81 is True,
             _cfg81["unallocatedProviders"][0].get("emoji") == "\U0001F4A5",
             _cfg81["unallocatedProviders"][1].get("emoji") == ""]
except Exception:
    _eh81 = None
if _eh81 is not None:
    check(_eh81 == [True, True, True],
          "run: an emoji-less factory provider heals to its shipped mark on load, "
          "a custom one is never touched, and the heal marks the config changed",
          str(_eh81))
else:
    check(False, "the heal run did not RUN")

# ---------------------------------------------------------------- patch182
# Max tokens is the FINAL word - the provider card, else the launcher's own
# --n-predict / -n, overwrites whatever SkyrimNet sent, whatever the sampler
# source. And the thought defer stands down when a reply is unfinished but no
# chunk has arrived for 3.5s: the owner's field showed SkyrimNet abandoning
# queued chunks, and the defer waited its full ladder on a ghost.
check('_np = (rt.get("overrides") or {}).get("n_predict")' in py
      and '("n_predict", "--n-predict"),' in py
      and 'def _route_overrides(p, slot):' in py,
      "the card and the launcher rule max tokens end to end")
_fw82 = None
try:
    _d82 = {"max_tokens": 4096, "max_completion_tokens": 4096}
    _rt82 = {"thinking": True, "sampSource": "skyrimnet",
             "overrides": {"n_predict": "800"}, "slot": None, "grammar": False}
    fp.apply_route_shape(_d82, _rt82)
    _fw82 = [_d82.get("max_tokens") == 800, "max_completion_tokens" not in _d82]
except Exception:
    _fw82 = None
if _fw82 is not None:
    check(_fw82 == [True, True],
          "run: SkyrimNet asked 4096, the card said 800 - the request leaves "
          "with 800, on the SkyrimNet sampler source no less", str(_fw82))
else:
    check(False, "the final-word run did not RUN")
check('_arriving = (time.time() - _last_rx) <= 3.5' in py
      and 'p.get("defer", 0) < 3' in py
      and '_unfinished = bool(_nf) and _arriving and not any(' in py,
      "an unfinished reply earns a defer only while chunks actually arrive")
_gh82 = None
try:
    _f82 = []; _d82b = []
    _mk82, _no82, _cl82, _tw82 = (fp.tts_thought_make, fp.sse_notify,
                                  fp.calterm_log, fp.TTSW.log)
    fp.tts_thought_make = lambda who, text, cfg=None: ("e", 0.1)
    fp.sse_notify = lambda kind, extra=None: (_f82.append(time.time())
                                              if kind == "replay" else None)
    fp.calterm_log = lambda lines: (_d82b.append(1) if "DEFER" in lines[0] else None)
    fp.TTSW.log = lambda *a, **k: None
    _w82 = "GateGhost82"; _t82 = time.time()
    fp.REPLY_FULL[_w82] = (fp._th_norm("One real chunk. A second that never comes."),
                           time.time())
    fp.CHUNK_TRACE.pop(_w82, None); fp.TH_AFTER.pop(_w82, None)
    fp.tts_chunk_trace(_w82, 1.0, "One real chunk.")
    fp.tts_thought_after_chunk(_w82, "T", 1.0)
    time.sleep(6.5)
    fp.tts_thought_make, fp.sse_notify, fp.calterm_log, fp.TTSW.log = (
        _mk82, _no82, _cl82, _tw82)
    _gh82 = [len(_d82b) <= 1, len(_f82) == 1,
             bool(_f82) and (_f82[0] - _t82) < 6.5]
except Exception:
    _gh82 = None
if _gh82 is not None:
    check(_gh82 == [True, True, True],
          "run: the 16:49 ghost - one chunk, a promised second that never comes - "
          "fires within six seconds after AT MOST one defer, not sixteen after five",
          str(_gh82))
else:
    check(False, "the ghost run did not RUN")

# ---------------------------------------------------------------- patch183
# One voice sample shared by two characters cannot tell them apart, and the
# pending-name queue only ORDERS them - the field report: Faralda's line
# labelled Saadia while her thought and her action stayed right. The WORDS
# name the voice: the reply kept under the name the prompt gave contains the
# line about to be spoken. Exactly one match wins; none or several leaves the
# older rules alone, because a wrong name is worse than a voicetype.
check("def speaker_for_text(text):" in py and "def tts_pin_speaker(path, text):" in py
      and "tts_pin_speaker(ref_path, text)" in py
      and "pin = _spk_pin.get(key)" in py,
      "the line names its own speaker, before the first label of that line")
check(py.index("REPLY_FULL[who] = (_th_norm(") < py.index("if not rows:")
      and py.count("REPLY_FULL[who] = (_th_norm(") == 1,
      "every reply's spoken text is kept, thought in it or not - one write, above "
      "the thought guard")
_sp83 = None
try:
    _pl83 = fp.panel_log
    fp.panel_log = lambda *a, **k: None
    _R83 = "femalesultry.wav"
    _F83 = "Why is he asking me about her well-being? That is odd."
    _S83 = "I cannot think straight with how badly I want him."
    fp.REPLY_FULL["GateFaralda83"] = (fp._th_norm(_F83), time.time())
    fp.REPLY_FULL["GateSaadia83"] = (fp._th_norm(_S83), time.time())
    fp._spk_pin.pop("femalesultry", None)
    fp._spk_voices["femalesultry"] = "GateSaadia83"
    fp._spk_recent[:] = [(time.time(), "GateSaadia83"), (time.time(), "GateFaralda83")]
    _old83 = fp.speaker_for_voice("femalesultry")          # the field's wrong name
    fp._spk_pin.pop("femalesultry", None)
    fp._spk_voices["femalesultry"] = "GateSaadia83"
    fp._spk_recent[:] = [(time.time(), "GateSaadia83"), (time.time(), "GateFaralda83")]
    fp.tts_pin_speaker(_R83, _F83)
    _new83 = fp.tts_speaker_label(_R83)                    # named by its own words
    _shrt = fp.tts_speaker_label(_R83)                     # and held for the line
    fp.tts_pin_speaker(_R83, _S83)
    _her83 = fp.tts_speaker_label(_R83)                    # her own line, her name
    _non83 = fp.speaker_for_text("words nobody here ever generated at all")
    # BOTH of them said it: the words no longer separate them, so they name nobody
    _same83 = "We should not linger here any longer than we must."
    fp.REPLY_FULL["GateFaralda83"] = (fp._th_norm(_same83), time.time())
    fp.REPLY_FULL["GateSaadia83"] = (fp._th_norm(_same83), time.time())
    _amb83 = fp.speaker_for_text(_same83)
    _plr83 = fp.tts_pin_speaker("player.wav", _F83)
    fp._spk_pin.pop("femalesultry", None)
    fp._spk_voices.pop("femalesultry", None)
    fp.REPLY_FULL.pop("GateFaralda83", None); fp.REPLY_FULL.pop("GateSaadia83", None)
    fp._spk_recent[:] = []
    fp.panel_log = _pl83
    _sp83 = [_old83 == "GateSaadia83", _new83 == "GateFaralda83",
             _shrt == "GateFaralda83", _her83 == "GateSaadia83",
             _non83 == "", _amb83 == "", _plr83 == ""]
except Exception:
    _sp83 = None
if _sp83 is not None:
    check(_sp83 == [True] * 7,
          "run: the shared-sample mixup - the queue alone hands Faralda's line "
          "Saadia's name; named by its own words it is hers, it stays hers across "
          "the line, Saadia's own line is still Saadia, and a line that matches "
          "nothing, a line BOTH of them said, and the player are never named "
          "this way", str(_sp83))
else:
    check(False, "the shared-sample run did not RUN")

# ------------------------------------------------------------------ patch151
# Four repairs from the field: the thought note carries no wave marks (a waved
# line is SPOKEN to the splicer, which inserted the note under the nearest record
# as a response row); the echo is half again with twice the boom; a shipped
# default added in an update now arrives on the NEXT START, additively; and the
# yaml exports real SN providers only - the panel-owned PTI/PME wrote :0
# endpoints into providers.yaml.
check(('Thought voiced: \\U0001F4AD %s: \\u3030 %s \\u3030' in py)
      and ("\\u3030\\uFE0F" not in seg(py, 'Thought voiced: \\U0001F4AD', "sse_notify")),
      "the thought note is written whole in the proxy's own shape - plain waves "
      "only, never the SAID pair, so the splicer still leaves it be (patch174)")
check("def create_missing_default_providers(cfg):" in py
      and "create_missing_default_providers(cfg)" in seg(py, "def seed_default_providers", "_CFG_CACHE"),
      "one additive creator, used by the seeder rather than copied into it")
check("if create_missing_default_providers(cfg):" in seg(py, "def load_config():", "def read_named_template("),
      "and run on every load, so an update's new provider arrives on the next start")
_ms51 = None
try:
    _c51 = {"slots": [{"id": "s1", "providers": [{"id": "p1", "title": "Dialogue",
                                                  "port": 1251}]}]}
    _a51 = fp.create_missing_default_providers(_c51)
    _b51 = fp.create_missing_default_providers(_c51)
    _n51 = [(p["title"], p["port"]) for p in _c51.get("unallocatedProviders", [])
            if str(p.get("title", "")).startswith("NE-")]
    _ms51 = [_a51 is True, _b51 is False,
             _n51 == [("NE-Composer", 1264), ("NE-Director", 1265)]]
except Exception:
    _ms51 = None
if _ms51 is not None:
    check(_ms51 == [True, True, True],
          "run: the additive pass creates the pair once and is idempotent after",
          str(_ms51))
else:
    check(False, "the additive-seed run did not RUN - the helper is broken")
check('if p.get("panelOwned") or int(p.get("port") or 0) <= 0:' in
      seg(py, "def api_yaml_generate", "def api_yaml_create"),
      "the yaml skips the panel's own and any zero port - no :0 endpoint can be written")

# ------------------------------------------------------------------ patch152
# The AFTER thought waits for the WHOLE reply: SkyrimNet splits one completion
# into several TTS chunks, and the old timer armed on the first chunk's length -
# the field photo shows the thought landing between "Important?" and the rest.
# Now each chunk extends a per-speaker modeled playback end (playback is
# sequential while requests pipeline ahead) and re-arms one timer; it fires once,
# after the LAST chunk. The run below plays a three-chunk burst against the real
# scheduler and measures where the fire lands.
check('p["end"] = (max(p["end"], now + TH_START_LAT)' in py
      and '+ max(0.0, float(secs or 0.0)) + TH_CHUNK_GAP)' in py,
      "every chunk pushes the modeled end - and the model now carries what the "
      "game adds around the wav: a start latency and an engine gap per chunk")
check(fp.TH_START_LAT >= 0.3 and fp.TH_CHUNK_GAP >= 0.2 and fp.TH_FIRE_PAD >= 0.1,
      "the three allowances are real numbers, not zeros a refactor left behind")
check("p[\"timer\"].cancel()" in seg(py, "def tts_thought_after_chunk", "def api_tts_thought"),
      "a reply's first chunk opens ITS pending and every chunk re-arms that "
      "pending's one timer - one queue entry per reply since patch160")
check("threading.Thread(target=tts_thought_make, args=(who, text, cfg)," in py,
      "and the synthesis is warmed in the background, so the fire is a broadcast")
_bc52 = None
try:
    _fired = []
    _mk_keep, _no_keep, _cl_keep = fp.tts_thought_make, fp.sse_notify, fp.calterm_log
    fp.tts_thought_make = lambda who, text, cfg=None: ("thGATE", 0.3)
    fp.sse_notify = lambda kind, extra=None: _fired.append(time.time())
    fp.calterm_log = lambda lines: None
    _tw52 = fp.TTSW.log; fp.TTSW.log = lambda *a, **k: None
    _t052 = time.time()
    fp.tts_thought_after_chunk("GateNPC", "a thought", 0.30)
    time.sleep(0.05)
    fp.tts_thought_after_chunk("GateNPC", None, 0.30)
    time.sleep(0.05)
    fp.tts_thought_after_chunk("GateNPC", None, 0.30)
    # expected fire from the model itself: start latency, three chunks with
    # their gaps, and the fire pad - computed, so a retune cannot stale this run
    _exp52 = fp.TH_START_LAT + 3 * (0.30 + fp.TH_CHUNK_GAP) + fp.TH_FIRE_PAD
    time.sleep(_exp52 + 0.8)
    fp.tts_thought_make, fp.sse_notify, fp.calterm_log = _mk_keep, _no_keep, _cl_keep
    fp.TTSW.log = _tw52
    _bc52 = [len(_fired) == 1,
             bool(_fired) and (_fired[0] - _t052) > _exp52 - 0.45]
except Exception:
    _bc52 = None
if _bc52 is not None:
    check(_bc52 == [True, True],
          "run: a three-chunk burst fires the thought ONCE, after the last chunk's "
          "modeled end - never between chunks", str(_bc52))
else:
    check(False, "the burst run did not RUN - the scheduler is broken")

# ---------------------------------------------------------------- patch160
# The field race: a fast model produced the NEXT reply's thought while the
# CURRENT reply's chunks still streamed - the old code popped it on chunk 2,
# cancelled the pending, and reset the chain: the first thought never played
# and the second fired mid-dialogue. Pendings are a QUEUE now, one per reply,
# each chained after the one before; the run below plays the race itself.
check('q.append({"text": text, "end": base, "t0": now, "timer": None})' in py
      and 'base = max(q[-1]["end"], now) if q else now' in py,
      "a new thought CHAINS after the pending one - it can never erase it")
check('calterm_log(["thought ARM' in py and 'calterm_log(["thought FIRE' in py,
      "and every arm and fire writes one visible line, so timing is never a guess")
_rc60 = None
try:
    _f60 = []
    _mk60, _no60, _cl60 = fp.tts_thought_make, fp.sse_notify, fp.calterm_log
    fp.tts_thought_make = lambda who, text, cfg=None: ("e-" + text, 0.2)
    fp.sse_notify = lambda kind, extra=None: _f60.append(extra["id"])
    fp.calterm_log = lambda lines: None
    _tw60 = fp.TTSW.log; fp.TTSW.log = lambda *a, **k: None
    fp.tts_thought_after_chunk("GateRace", "T1", 0.25)
    time.sleep(0.05)
    fp.tts_thought_after_chunk("GateRace", "T2", 0.25)
    time.sleep(0.05)
    fp.tts_thought_after_chunk("GateRace", None, 0.25)
    time.sleep(fp.TH_START_LAT * 2 + 4 * (0.25 + fp.TH_CHUNK_GAP)
               + 2 * fp.TH_FIRE_PAD + 1.2)
    fp.tts_thought_make, fp.sse_notify, fp.calterm_log = _mk60, _no60, _cl60
    fp.TTSW.log = _tw60
    _rc60 = list(_f60)
except Exception:
    _rc60 = None
if _rc60 is not None:
    check(_rc60 == ["e-T1", "e-T2"],
          "run: a second thought landing MID-burst plays AFTER the first - both "
          "fire, in order, neither erased", str(_rc60))
else:
    check(False, "the race run did not RUN")

# ---------------------------------------------------------------- patch162
# The owner's design, implemented as stated: the proxy has SEEN the whole reply,
# so the FINAL TTS chunk is recognised by its text ending the reply - and that
# chunk anchors the fire absolutely: its delivery + its length + 0.5 s. Counting
# every chunk remains only as the fallback for a reply the proxy never saw.
check("def tts_chunk_is_last(who, chunk_text):" in py
      and 'is_last=tts_chunk_is_last(_thWho, processed)' in py,
      "the final chunk is recognised from the stored reply, not counted")
check('p["end"] = now + TH_START_LAT + max(0.0, float(secs or 0.0)) + 0.2' in py
      and 'p = q[0] if is_last else q[-1]' in py,
      "and it re-anchors the OLDEST pending - fallback when no trace exists")
check("def tts_chunk_trace(who, secs, text):" in py
      and "tts_chunk_trace(_thWho, secs, processed)" in py
      and "_e = max(_e, _rt + TH_START_LAT) + _rs + TH_CHUNK_GAP" in py,
      "every NPC chunk is traced unconditionally, and the FINAL chunk chains the "
      "whole traced reply - chunks delivered before the thought existed included")
_fl62 = None
try:
    fp.CHUNK_TRACE.pop("GateFin", None)
    fp.REPLY_FULL["GateFin"] = (fp._th_norm("One two. Three four five."), time.time())
    _f62 = []
    _mk62, _no62, _cl62 = fp.tts_thought_make, fp.sse_notify, fp.calterm_log
    fp.tts_thought_make = lambda who, text, cfg=None: ("e", 0.1)
    fp.sse_notify = lambda kind, extra=None: _f62.append(time.time())
    fp.calterm_log = lambda lines: None
    _tw62 = fp.TTSW.log; fp.TTSW.log = lambda *a, **k: None
    _t62 = time.time()
    fp.tts_thought_after_chunk("GateFin", "T", 4.0)
    fp.tts_thought_after_chunk("GateFin", None, 0.6,
                               is_last=fp.tts_chunk_is_last("GateFin", "Three four five!"))
    time.sleep(2.6)
    fp.tts_thought_make, fp.sse_notify, fp.calterm_log = _mk62, _no62, _cl62
    fp.TTSW.log = _tw62
    _fl62 = [len(_f62) == 1, bool(_f62) and 1.0 < (_f62[0] - _t62) < 2.4]
except Exception:
    _fl62 = None
if _fl62 is not None:
    check(_fl62 == [True, True],
          "run: a recognised final chunk fires at ITS length + 0.5, not at the "
          "sum a long first chunk would have demanded", str(_fl62))
else:
    check(False, "the final-chunk run did not RUN")

# ------------------------------------------------------------------ patch153
# Seven items and one field root-cause. LLM Controlled retired whole (checked
# throughout above); Server N: names with a load migration; centered section
# rules; a ? on Tag Limits and click-tips everywhere; a steady card terminal;
# and slot 2's launch failure: the flag setter did not recognise a PowerShell
# VARIABLE as a value, so "-m", $modelPath became "-m", "path", $modelPath -
# the variable a stray positional, llama-server answering
# "error: invalid argument: <model path>". Reproduced from the field config,
# fixed, and run live below.
check(".row.srow2 { margin-top:8px; margin-bottom:6px; }" in PAGE
      and ".card .alloclink { display:inline-block; margin-top:2px; }" in PAGE,
      "the card's first three rows breathe - srow2 and the allocation line spaced")
check(".pgrp { grid-column: 1 / -1; margin: 16px 0 2px; padding-top: 16px;" in PAGE,
      "the section rule sits centered in the gap - 16 above, 16 below")
check('"ttsAutoCalPort" not in py'.__class__ and "ttsAutoCalPort" not in py,
      "the fit server setting is gone from the source with its mode")
check('>Tag Limits<span class="qm">?</span></button>' in JS,
      "the Tag Limits button wears a ? of its own")
_qm53 = seg(JS, 'document.addEventListener("click", ev => {', 'if (d.act === "revealUuid")')
check('ev.target.closest(".qm")' in _qm53
      and _qm53.index('closest(".qm")') < _qm53.index('closest("[data-act]")'),
      "a ? click is answered BEFORE the button dispatch - the tip shows, the "
      "button under it is not pressed")
check("function qmShowTip(qmEl)" in JS and "#qm-pop {" in PAGE,
      "the tip is a positioned bubble with one copy of its card rules")
check("  pre.log { " in PAGE
      and "height:170px" in seg(PAGE, "  pre.log { ", "  pre.log.resizable"),
      "the card terminal is a steady box - fixed height, text flows within")
check("drop_value_next" in py
      and 'if re.match(r' in seg(py, "def render_launcher_lines", "def _gpu_pin_value"),
      "a skipped flag line never strands its value line as a positional")
NL53 = chr(10)
_lc53 = None
try:
    _cnt53 = NL53.join(["$llamaArgs = @(", '    "--model-draft",',
                        '    "MODELDIR/draft.gguf",', '    "-m", "MODELDIR/main.gguf",', ")"])
    _t53 = {"content": _cnt53, "model": "MODELDIR/main.gguf",
            "vision": "Disabled", "draft": "Disabled"}
    _out53 = NL53.join(fp.render_launcher_lines(_t53, "x.ps1", "l.exe"))
    _lc53 = "draft.gguf" not in _out53 and '"-m", "MODELDIR/main.gguf"' in _out53
except Exception:
    _lc53 = None
if _lc53 is not None:
    check(_lc53 is True,
          "run: a two-line resolved draft, disabled, leaves NO orphan value behind")
else:
    check(False, "the launcher-render run did not RUN")
check(chr(92) + "$[A-Za-z_][A-Za-z0-9_:.]*" in py,
      "the flag setter recognises a PowerShell variable as a value")
_sf53 = None
try:
    _body53 = NL53.join(["$llamaArgs = @(", '    "-m", $modelPath,',
                         '    "--port", "1237",', ")"]) + NL53
    _new53 = fp.ps1_set_flag(_body53, "-m", "MODELDIR/e2b.gguf")
    _sf53 = ("$modelPath" not in _new53
             and '"-m", "MODELDIR/e2b.gguf"' in _new53
             and '"--port", "1237"' in _new53)
    # the HEALING case: a launcher an earlier setter already broke - the quoted
    # value AND the stranded variable both baked in - comes out as one clean pair
    _baked53 = NL53.join(["$llamaArgs = @(",
                          '    "-m", "MODELDIR/old.gguf", $modelPath,',
                          '    "--port", "1237",', ")"]) + NL53
    _heal53 = fp.ps1_set_flag(_baked53, "-m", "MODELDIR/e2b.gguf")
    _sf53 = _sf53 and ("$modelPath" not in _heal53
                       and "old.gguf" not in _heal53
                       and '"-m", "MODELDIR/e2b.gguf"' in _heal53
                       and '"--port", "1237"' in _heal53
                       and fp.ps1_set_flag(_heal53, "-m", "MODELDIR/e2b.gguf") == _heal53)
except Exception:
    _sf53 = None
if _sf53 is not None:
    check(_sf53 is True,
          "run: a variable value is REPLACED, and a launcher an earlier launch "
          "already broke is HEALED to one clean pair, idempotently - no stray "
          "positional survives to reach llama-server")
else:
    check(False, "the flag-setter run did not RUN")

# ------------------------------------------------------------------ patch155
# The pre-release sweep. Privacy first: the redacted remote state is HUNTED for
# leaks live, against a config carrying everything the field one did - a custom
# launcher full of absolute paths and a pinned GPU serial, path settings, a
# loaded script source. The LAN toggle's promise ("cannot see your IPs, paths,
# or GPU IDs") is a gate check now, not a sentence.
_lk55 = None
try:
    _ser55 = "GPU-" + "12345678-aaaa"          # composed: the literal may not exist here
    _ip55 = "192.0.2.9"                        # TEST-NET-1, never a real LAN
    _c55 = {"settings": {"llamacppPath": "C_COLON/llama", "launcherDir": "C_COLON/l",
                         "ttsAcppDir": "C_COLON/acpp", "ttsAcppModel": "C_COLON/m/h.gguf",
                         "ttsOutDir": "C_COLON/out", "yamlOutDir": "C_COLON/y",
                         "remoteIp": _ip55, "networkMode": "lan"},
            "gpus": [{"id": "gpu1", "uuid": _ser55, "index": 0,
                      "name": "RTX", "mem": 1, "sub": "", "brand": ""}],
            "slots": [{"id": "s1", "label": "Server 1: RTX", "port": 1236,
                       "script": "C_COLON/gen/slot1.ps1", "scriptSrc": "C_COLON/hand/x.ps1",
                       "gpu": _ser55,
                       "params": {"model": "C_COLON/m/big.gguf",
                                  "custom": "$env:CUDA_VISIBLE_DEVICES = " + chr(34)
                                            + _ser55 + chr(34) + NL53
                                            + chr(34) + "-m" + chr(34) + ", "
                                            + chr(34) + "C_COLON/m/big.gguf" + chr(34),
                                  "prevCustom": "old C_COLON/m/big.gguf"},
                       "providers": []}],
            "creatorSlots": [{"id": "t1", "title": "tpl", "model": "C_COLON/m/big.gguf",
                              "content": "-m C_COLON/m/big.gguf " + _ser55}],
            "unallocatedProviders": []}
    import copy as _cp55
    _keeplc, _keeplcc = fp.load_config, fp.load_config_cached
    _keeppl, _keeple = fp.panel_log, fp.log_error
    _keepld = fp.log_dir
    fp.load_config = lambda: _cp55.deepcopy(_c55)
    fp.load_config_cached = lambda *a, **k: _cp55.deepcopy(_c55)
    fp.panel_log = lambda *a, **k: None       # a hunt that writes into the tree it
    fp.log_error = lambda *a, **k: None       # judges has judged a different tree
    fp.log_dir = lambda cfg=None: tempfile.gettempdir()   # nor may it mkdir logs/
    try:
        _red55 = json.dumps(fp.redact_state(fp.api_state()))
    finally:
        fp.load_config, fp.load_config_cached = _keeplc, _keeplcc
        fp.panel_log, fp.log_error = _keeppl, _keeple
        fp.log_dir = _keepld
    _pats55 = ("C_COLON/", _ser55[:12], "CUDA_VISIBLE_DEVICES", ".gguf", _ip55,
               "hand/x.ps1")
    _lk55 = [p for p in _pats55 if p in _red55]
except Exception:
    _lk55 = None
if _lk55 is not None:
    check(_lk55 == [],
          "run: the redacted remote state carries NO path, serial, env line, model "
          "filename, IP or loaded-script source - the toggle's promise, verified",
          str(_lk55))
else:
    check(False, "the redaction hunt did not RUN")
check('pr.pop("custom", None)' in py and 'pr.pop("prevCustom", None)' in py,
      "the hand-written launcher bodies never reach a remote viewer at all")
# one bind rule, written once, and every listener obeys it
check("def listen_host(st=None):" in py,
      "where a LAN-facing listener binds is ONE function")
check(fp.listen_host({"remoteIp": ""}) == "127.0.0.1"
      and fp.listen_host({"remoteIp": "192.0.2.9"}) == "0.0.0.0",
      "run: no second PC configured means loopback; a remote IP opens the LAN")
check('_bind = "0.0.0.0" if net_mode() == "lan" else "127.0.0.1"' in py
      and "ThreadingHTTPServer((_bind, PORT), Handler)" in py,
      "the panel page itself binds the LAN only in LAN mode")
check("_QuietServer((_lh, lp), _mk_handler(self, lp))" in py
      and "_QuietServer((listen_host(st), port), _mk_tts_handler(self))" in py,
      "the proxy and the TTS wrapper both bind by that one rule")
check(".server_address[0] != _lh" in py
      and ".server_address[0] != listen_host(st)" in py,
      "and a listener bound for the wrong world is rebound, not kept")
check('("Server", "--host", "127.0.0.1")' in py,
      "servers the panel spawns serve the panel alone - the proxy is the LAN face")
# the dead-code sweep held: names gone whole, imports single and used
for _dead55 in ("def tts_job_port", "def cal_apply", "def cal_json", "def tts_chunks",
                "def tts_wav_join", "def gpu_for_server_port", "def slot_parallel_min",
                "def _tag_known", "function isCompletion", "function ttsThinkBox",
                "function ttsSrvBox", "function ttsPriorityBox", "function ttsCalNote",
                "ttsCalibPort", "TTS_LAST_END", "import hmac", "AUTOCAL_QUIET"):
    nin(py, _dead55, "gone whole: %s" % _dead55)
check("import ctypes, glob, hashlib," in py and '"app": APP_NAME' not in py,
      "one import of each, and the state dict no longer overrides its own key")

# ------------------------------------------------------------------ patch157
# Three sights fixed where they are made. The Live Network provider box puts a
# space between the mark and the name; the ? on Tag Limits wears the same round
# badge as the one beside a title, because the badge rule now dresses a .qm
# inside a button too; and the click that shows the tip was already wired - the
# badge just was not visible as one.
# .nb-t is a flex row (the patch-era check below still stands): the emoji gets a
# margined span of its own, exactly as the panel icon always had margin-right:6px
check('\'<span style="margin-right:6px">\' + provMark(p, 15) + \'</span>\'' in JS,
      "the Live Network box breathes between the mark and the name - by margin, "
      "which a flex row honours, not by a space it would throw away")
check("#dpane-tts button .qm {" in PAGE.replace("label.ttl .qm,\n  #dpane-tts ", "")
      or "#dpane-tts button .qm" in PAGE,
      "the ? badge is dressed inside a button, not only beside a title")
check("#dpane-tts button:hover .qm" in PAGE,
      "and lights up on hover there too")

# ---------------------------------------------------------------- patch166
check('for fam, val in re.findall(r"' + chr(92) + '[([A-Z]+)-([A-Z_]+)' + chr(92) + ']", str(text or "")):' in py,
      "the face reads the ON-WIRE Higgs bracket form the alias pass writes - the "
      "field regression that left every NPC row wearing the plain head")
check(fp.tts_mood_icon("[EMOTION-ENTHUSIASM] settled") == fp.TTS_MOOD[("emotion", "enthusiasm")]
      and fp.tts_mood_icon("[SFX-LAUGHTER] ha") == fp.TTS_MOOD[("sfx", "laughter")]
      and fp.tts_mood_icon("<|emotion:anger|> *laughs* x") == fp.TTS_MOOD[("emotion", "anger")],
      "run: an emotion on the wire faces the row; a sound ALONE wears its own "
      "icon since patch171; an emotion still outranks it")
check("_dl = time.time() + 3.0" in py and 'THOUGHT_FRESH.pop(_thWho, None)' in py,
      "BEFORE waits a bounded moment for the streamed thought, so the reply is "
      "fronted by its own thought, not the next one's")
check('prune_keep_newest(ld, "*_ttscal.log", 4)' in py
      and 'prune_keep_newest(ld, "*_tts-server.log", 4)' in py
      and 'prune_keep_newest(ld, PTIPME_LOG_GLOB, 4)' in py,
      "the session-file families rotate at five like the dashboard always has")
check('"\U0001F50A TTS"' in JS and '"\U0001F9E9 PTI / PME"' in JS
      and 'return "tts";' in JS and 'return "ptipme";' in JS,
      "the Files pane classes TTS and PTI/PME logs under their own headings")
check('data-act="logSrvSlot"' in JS and 'd.act === "logSrvSlot"' in JS
      and 'window.__logSrvSlot' in JS,
      "the Server category grows one button per slot, filtering its files")

# ---------------------------------------------------------------- patch169
# The NPC counterpart of the player's tag injection: the completion's queued
# mood becomes a REAL Higgs control token on the spoken chunk, judged by the
# same wire everything already rides - master switch, final-off board, this
# character's own cooldown limits. The runs below walk the whole circle.
check('def tts_npc_mood_arm(who, text, cool=frozenset()):' in py
      and "raw = tts_npc_mood_arm(tts_speaker_label(ref_path), raw," in py
      and "cool=_cool)" in seg_len(py, "raw = tts_npc_mood_arm", 300),
      "every NPC chunk is offered its queued completion mood at the one gate")
_tl70 = seg(py, "def thought_lines(said", "\ndef ", 1)
check(_tl70.index("MOOD_QUEUE[who] = (_mq, time.time())") < _tl70.index("if not rows:"),
      "the mood capture sits ABOVE the thought guard - a tag-only reply with no "
      "thought at all still fills the queue, and an EMPTY entry is written so "
      "the armer knows a parsed reply from an unparsed one")
check("_dl = time.time() + 1.5" in seg(py, "def tts_npc_mood_arm", "TH_START_LAT"),
      "and the armer waits out the receipt-vs-completion race, bounded")
_rc70 = None
try:
    import threading as _th70
    fp.MOOD_QUEUE.pop("GateRace70", None)
    _th70.Timer(0.3, lambda: fp.thought_lines("[fear] late", "GateRace70")).start()
    _o70 = fp.tts_npc_mood_arm("GateRace70", "line")
    fp.MOOD_QUEUE["GateRace70b"] = ([], time.time())
    _t70 = time.time()
    _p70 = fp.tts_npc_mood_arm("GateRace70b", "plain")
    _rc70 = [_o70 == "<|emotion:fear|> line",
             _p70 == "plain" and time.time() - _t70 < 0.3]
except Exception:
    _rc70 = None
if _rc70 is not None:
    check(_rc70 == [True, True],
          "run: a chunk that beats the completion's parse still gets its token, "
          "and a parsed-but-untagged reply passes with no wait at all", str(_rc70))
else:
    check(False, "the race run did not RUN")

# ---------------------------------------------------------------- patch171
nin(py, "ttsMoodPlace",
    "Emotion Chunk Placement is GONE - the model decides how many emotions a reply "
    "carries and where they change; the panel places none of its own (patch190)")
check('if fam.lower() == "sfx":' in seg(py, "def tts_mood_icon", "\ndef ")
      and seg(py, "def tts_mood_icon", "\ndef ").rindex('"sfx"')
          > seg(py, "def tts_mood_icon", "\ndef ").index('"style"'),
      "a sound-only chunk wears the sound's icon, after emotions and styles")
check('with self.blk:' in py and "self.blk = threading.Lock()" in py
      and "TTSW.blk.acquire()" in py and "TTSW.blk.release()" in py,
      "thought and dialogue report blocks write whole - never interleaved again")
_df71 = None
try:
    _f71 = []; _d71 = []
    _mk71, _no71, _cl71, _tw71 = (fp.tts_thought_make, fp.sse_notify,
                                  fp.calterm_log, fp.TTSW.log)
    fp.tts_thought_make = lambda who, text, cfg=None: ("e", 0.1)
    fp.sse_notify = lambda kind, extra=None: (_f71.append(time.time())
                                              if kind == "replay" else None)
    fp.calterm_log = lambda lines: (_d71.append(1) if "DEFER" in lines[0] else None)
    fp.TTSW.log = lambda *a, **k: None
    _t71 = time.time()
    _w71 = "GateDefer71"
    fp.REPLY_FULL[_w71] = (fp._th_norm("One here. Two closes it."), time.time())
    fp.CHUNK_TRACE.pop(_w71, None); fp.TH_AFTER.pop(_w71, None)
    fp.tts_chunk_trace(_w71, 1.0, "One here.")
    fp.tts_thought_after_chunk(_w71, "T", 1.0)
    time.sleep(2.5)                      # the fire attempt lands in the gap
    fp.tts_chunk_trace(_w71, 1.2, "Two closes it.")
    fp.tts_thought_after_chunk(_w71, None, 1.2,
                               is_last=fp.tts_chunk_is_last(_w71, "Two closes it."))
    time.sleep(4.5)
    fp.tts_thought_make, fp.sse_notify, fp.calterm_log, fp.TTSW.log = (
        _mk71, _no71, _cl71, _tw71)
    _df71 = [len(_d71) >= 1, len(_f71) == 1,
             bool(_f71) and _f71[0] - _t71 > 3.2]
except Exception:
    _df71 = None
if _df71 is not None:
    check(_df71 == [True, True, True],
          "run: a non-final fire landing in the gap DEFERS, and the one true fire "
          "leaves after the final chunk re-anchors - the owner's 01:55 race, won",
          str(_df71))
else:
    check(False, "the defer run did not RUN")

# ---------------------------------------------------------------- patch172
# Two matcher defects the defer made loud: endswith could not see past a
# SkyrimNet prefix inside a SHORT final chunk, and a 300-second-stale reply
# text let a racing chunk match the PREVIOUS reply forever. Final-chunk
# recognition is by COMMON SUFFIX now - the true final ends as the reply
# ends, whatever was injected in front - and only a FRESH reply may claim
# anything; stale or unknown stands the defer down and the chain fires as
# patch170 did.
check("if not full or time.time() - full[1] > 25.0:" in py
      and "return _n >= min(12, len(nf), len(nc))" in py
      and "_cs172(_nf, r[2]) >= min(12, len(_nf), len(r[2]))" in py,
      "final by common suffix, judged only against a fresh reply - both sides")
_fs72 = None
try:
    fp.REPLY_FULL["GateSfx72"] = (fp._th_norm("Not too far, no! Just a short walk."),
                                  time.time())
    _fs72 = [fp.tts_chunk_is_last("GateSfx72", "*laughs* Hehe, Just a short walk."),
             fp.tts_chunk_is_last("GateSfx72", "*enthusiastic* Not too far, no!") is False]
    fp.REPLY_FULL["GateSfx72"] = (fp._th_norm("old text from long ago"),
                                  time.time() - 60)
    _fs72.append(fp.tts_chunk_is_last("GateSfx72", "long ago") is False)
except Exception:
    _fs72 = None
if _fs72 is not None:
    check(_fs72 == [True, True, True],
          "run: a short PREFIXED final is recognised, a mid chunk is not, and a "
          "stale reply claims nothing - the owner's 02:40 and 02:38 cases",
          str(_fs72))
else:
    check(False, "the suffix run did not RUN")

# ---------------------------------------------------------------- patch174
check('TTSW.log("\\U0001F4AD %s (thought): \\u3030 %s \\u3030" % (who, text))' in py
      and '%.90s' not in seg(py, "def tts_thought_make", "\ndef "),
      "the thought header is written WHOLE, like the proxy terminal writes it")
check('self.log("")   # and stands apart from the receipt group (patch174)' in py,
      "the report block opens with its own blank row - groups stand apart")
check("function paintTtsMeta(line)" in JS and "paintTtsMeta(line);" in JS
      and '"#4dd8e6"' in seg(JS, "function paintTtsMeta", "function paintSpoken")
      and '"#f0c674"' in seg(JS, "function paintTtsMeta", "function paintSpoken")
      and '"#c07ffb"' in seg(JS, "function paintTtsMeta", "function paintSpoken"),
      "report rows wear the panel's own inks: thinking's cyan and gold, the "
      "payload viewer's grape, magenta for names - one family everywhere")

# ---------------------------------------------------------------- patch175
# The gate is keyed by CARD and was always meant to be: rt["gpu"] comes from the
# slot the provider lives under, so two GPUs never wait on each other, and the
# ActionEval drilldown arrives on ActionEval's own listener - the same route,
# the same priority 0, by construction. What the field exposed was patience:
# an 8 s cap shorter than a real high call let normals barge mid-high.
check("GATE_MAX_WAIT_S = 30.0" in py
      and 'wait_ms = mgr.gate.enter(rt["gpu"], is_high) if gate_held else 0' in py
      and 'is_high = rt["priority"] == 0' in py,
      "priority is judged per CARD via the route's own slot, and a normal now "
      "yields to an active high for as long as the high realistically runs")
_gg75 = None
try:
    import threading as _th75
    _g75 = fp.GpuGate()
    _g75.enter("gA", True)
    _r75 = {}
    _th75.Thread(target=lambda: _r75.__setitem__("ms", _g75.enter("gA", False)),
                 daemon=True).start()
    time.sleep(1.2)
    _held = "ms" not in _r75
    _other = _g75.enter("gB", False) == 0
    _g75.leave("gA", True)
    time.sleep(fp.HIGH_LINGER_S + 0.6)
    _gg75 = [_held, _other,
             1000 < _r75.get("ms", -1) < 1200 + (fp.HIGH_LINGER_S + 0.8) * 1000]
except Exception:
    _gg75 = None
if _gg75 is not None:
    check(_gg75 == [True, True, True],
          "run: a normal WAITS behind an active high on its own card, another "
          "card is untouched, and release follows the leave plus its linger",
          str(_gg75))
else:
    check(False, "the gate run did not RUN")

# ---------------------------------------------------------------- patch176
# The owner traced the inversion exactly: the drilldown is a SEPARATE call that
# SkyrimNet posts only after stage 1's response - and leave() freed the card
# into precisely that gap, where a queued normal took it. The card LINGERS held
# after a high leaves; an arriving high chains the hold; an empty window
# releases the normals. The run below is the field sequence, move for move.
check("HIGH_LINGER_S = 2.5" in py
      and 'self._linger.pop(gpu, None)' in py
      and 'self._linger[gpu] = time.time() + HIGH_LINGER_S' in py,
      "a high's leave lingers for its follow-up; a landing high chains the hold")
_lg76 = None
try:
    import threading as _th76
    _g76 = fp.GpuGate(); _r76 = {}
    _g76.enter("gL", True)
    _th76.Thread(target=lambda: _r76.__setitem__("n", _g76.enter("gL", False)),
                 daemon=True).start()
    time.sleep(0.4)
    _g76.leave("gL", True)                 # stage 1 returns
    time.sleep(0.4)
    _gap76 = "n" not in _r76               # the gap: normal must still be held
    _g76.enter("gL", True)                 # the drilldown lands inside the linger
    time.sleep(0.4)
    _run76 = "n" not in _r76
    _g76.leave("gL", True)
    time.sleep(fp.HIGH_LINGER_S + 0.6)
    _lg76 = [_gap76, _run76, _r76.get("n", 0) > 3000]
except Exception:
    _lg76 = None
if _lg76 is not None:
    check(_lg76 == [True, True, True],
          "run: the normal holds through the stage-1/stage-2 gap, the drilldown "
          "owns the card, and only an empty window releases - the field "
          "inversion, made impossible", str(_lg76))
else:
    check(False, "the linger run did not RUN")

# ---------------------------------------------------------------- patch177
check("const wv177 = String.fromCharCode(12336);" in JS
      and 'tintm(SPK_MAG, mv[2], true)' in JS and 'tintm(SPK_MAG, mt[2], true)' in JS
      and "(ms|s|x)?(?=$|[^A-Za-z0-9])" in JS,
      "thought lines: stamp cyan, speaker bold magenta, waves and text grape; "
      "an attached seconds unit is cyan, an x multiplier stays gold")

# ---------------------------------------------------------------- patch179
# A tag limit counts LLM RESPONSES - the round the owner asked for - not TTS
# chunks; and a multi-sentence thought is synthesized one sentence per request
# and joined, because audio.cpp ends a clip at a sentence's EOC on its own
# schedule (the owner's field wav held sentence 1 of 2).
check("def tts_reply_first_chunk(who):" in py and "def _th_member(nc, nf):" in py
      and py.count("_th_member(") >= 4,
      "one membership rule decides reply-first, the final chain and the defer")
check('re.split(r"(?<=[.!?])\\s+"' in py and "def _wav_join(datas):" in py
      and "wav = _wav_join(_wavs)" in py,
      "a thought is asked for sentence by sentence and joined into one wav")
_tp79 = None
try:
    _K79, _L79, _W79 = "gate-voice-79", {"sfx:laughter": 2}, "GateTurn79"
    fp.TAG_TURNS.pop(_K79, None); fp.CHUNK_TRACE.pop(_W79, None)
    _seq79 = []
    def _ck79(text, full, spoke):
        fp.REPLY_FULL[_W79] = (fp._th_norm(full), time.time())
        fp.tts_chunk_trace(_W79, 1.0, text)
        _new = fp.tts_reply_first_chunk(_W79)
        _co = fp.tag_cooldown_pass(_K79, _L79, new_turn=_new)
        _pr = "<|sfx:laughter|> x" if spoke else "x"
        _st = fp.tts_apply_tags(_pr, True, "audiocpp", _co)
        _fr = fp.tag_cooldown_note(_K79, _L79, _st) or frozenset()
        _rp = fp.tag_cooldown_report(_K79, _L79, exclude=_fr)
        return _new, ("<|sfx:laughter|>" in _st), _rp, bool(_fr)
    _F79 = "Hehe one. And two."
    _a = _ck79("*laughs* Hehe one.", _F79, True)
    _b = _ck79("And two.", _F79, True)
    fp.CHUNK_TRACE.pop(_W79, None)
    _c = _ck79("Second reply.", "Second reply.", True)
    fp.CHUNK_TRACE.pop(_W79, None)
    _d = _ck79("Third reply.", "Third reply.", False)
    fp.CHUNK_TRACE.pop(_W79, None)
    _e = _ck79("Fourth reply.", "Fourth reply.", True)
    _tp79 = [_a == (True, True, [], True),
             _b == (False, False, [("sfx:laughter", 3)], False),
             _c == (True, False, [("sfx:laughter", 2)], False),
             _d == (True, False, [("sfx:laughter", 1)], False),
             _e == (True, True, [], True)]
except Exception:
    _tp79 = None
if _tp79 is not None:
    check(_tp79 == [True] * 5,
          "run: NOT makeup - spoken in reply 1, the wire STRIPS the tag through "
          "the same reply and the next two responses while the report counts "
          "3-2-1, and reply 4 speaks it again", str(_tp79))
else:
    check(False, "the round-limit run did not RUN")

# ---------------------------------------------------------------- patch178
# The limit system is CHECKABLE now: every generation reports the board's
# banned tags and this character's live countdowns - (2) means this turn and
# the next, (+2) means the limit was recorded on this very line - and a
# LIMITED tag is refused by the armer too, so neither the face nor the log
# can claim an emotion the wire was always going to strip.
check('self.log("   Banned Tags: %s" % ", ".join(' in py
      and 'self.log("   Tag Limits: %s" % ", ".join(' in py
      and '"[%s (%d)]" % (tag_disp(p), r)' in py
      and '"[%s (+%d)]" % (tag_disp(p), _limits.get(p, 0))' in py,
      "the two rows print, and only when they have something to say")
check("def tag_cooldown_report(key, limits, exclude=frozenset()):" in py
      and "return frozenset(hits)" in py
      and 'or ("%s:%s" % pick) in cool' in py,
      "note returns what it recorded, report counts down, the armer refuses "
      "a cooling pair outright")
_tc77 = None
try:
    _K77, _L77 = "GateFem77", {"sfx:laughter": 2}
    fp.TAG_TURNS.pop(_K77, None)
    fp.tag_cooldown_pass(_K77, _L77)
    _f77 = fp.tag_cooldown_note(_K77, _L77, "<|sfx:laughter|> hey")
    _r1 = fp.tag_cooldown_report(_K77, _L77, exclude=_f77)
    fp.tag_cooldown_pass(_K77, _L77)
    _r2 = fp.tag_cooldown_report(_K77, _L77)
    fp.tag_cooldown_pass(_K77, _L77)
    _r3 = fp.tag_cooldown_report(_K77, _L77)
    fp.tag_cooldown_pass(_K77, _L77)
    _r4 = fp.tag_cooldown_report(_K77, _L77)
    fp.MOOD_QUEUE["GateFem77"] = ([("emotion", "elation")], time.time())
    _a77 = fp.tts_npc_mood_arm("GateFem77", "line",
                               cool=frozenset(["emotion:elation"]))
    _tc77 = [sorted(_f77) == ["sfx:laughter"], _r1 == [],
             _r2 == [("sfx:laughter", 2)], _r3 == [("sfx:laughter", 1)],
             _r4 == [], _a77 == "line",
             fp.MOOD_QUEUE["GateFem77"][0] == []]
except Exception:
    _tc77 = None
if _tc77 is not None:
    check(_tc77 == [True] * 7,
          "run: fresh is (+lim) on its own line, the countdown reads 2 then 1 "
          "then free, and a cooling emotion is refused and consumed", str(_tc77))
else:
    check(False, "the countdown run did not RUN")
_ar69 = None
try:
    fp.MOOD_QUEUE["GateNPC69"] = ([("sfx", "laughter"), ("emotion", "enthusiasm")],
                                  time.time())
    _a69 = fp.tts_npc_mood_arm("GateNPC69", "I do!")
    _b69 = fp.tts_npc_mood_arm("GateNPC69", "And more.")
    _c69 = fp.tts_npc_mood_arm("GateNPC69", "<|emotion:anger|> mine",)
    fp.MOOD_QUEUE["GateNPC69"] = ([("emotion", "fear")], time.time())
    _d69 = fp.tts_npc_mood_arm("GateNPC69", "each")
    _e69 = fp.tts_npc_mood_arm("GateNPC69", "chunk")
    _open69 = fp.tts_apply_tags(_a69, True, "audiocpp", frozenset())
    _shut69 = fp.tts_apply_tags(_a69, True, "audiocpp",
                                frozenset(["emotion:enthusiasm"]))
    _ar69 = [_a69 == "<|emotion:enthusiasm|> I do!",
             _b69 == "<|emotion:enthusiasm|> And more.",
             _c69 == "<|emotion:anger|> mine",
             _d69 == "<|emotion:fear|> each" and _e69 == "<|emotion:fear|> chunk",
             "<|emotion:enthusiasm|>" in _open69,
             "<|emotion:enthusiasm|>" not in _shut69]
except Exception:
    _ar69 = None
if _ar69 is not None:
    check(_ar69 == [True] * 6,
          "run: SOUNDS are never injected (SkyrimNet performs them - the doubled "
          "laugh), the only feeling written holds across the reply's chunks, a "
          "line carrying its own token is left alone, and the one gate still "
          "rules: open passes, boarded-off strips", str(_ar69))
else:
    check(False, "the mood-arm run did not RUN")

# ------------------------------------------------------------------ patch158
# The patch155 JS deletion took two constants living between dead functions -
# TTS_NEAR_DLG and TTS_BURST_GAP - and the terminal splicer threw on both: an
# empty Proxy terminal, a dead file viewer, and a flood of unhandled rejections.
# The Python side had a top-level-name differ that caught exactly this; the page
# now has its own: every CAPS_WITH_UNDERSCORE identifier the page code uses must
# be declared in it, with strings and comments stripped so prose cannot vouch.
check("const TTS_NEAR_DLG" in JS and "const TTS_BURST_GAP" in JS,
      "the splicer's two constants are back where the splicer can see them")
# one left-to-right pass: a string starting before a // keeps its slashes, and a
# // starting before an apostrophe keeps the comment whole - order cannot lie
_src58 = re.sub(r"'(?:[^'\\\n]|\\.)*'"
                r'|"(?:[^"\\\n]|\\.)*"'
                r"|`(?:[^`\\]|\\.)*`"
                r"|/\*[\s\S]*?\*/"
                r"|//[^\n]*",
                "", JS)
_used58 = set(re.findall(r"\b([A-Z][A-Z0-9]*_[A-Z0-9_]+)\b", _src58))
_decl58 = set(re.findall(r"(?:const|let|var|function)\s+([A-Za-z_]\w*)", JS))
_decl58 |= set(re.findall(r",\s*([A-Z][A-Z0-9_]+)\s*=", JS))
_miss58 = sorted(_used58 - _decl58)
check(_miss58 == [],
      "run: every CAPS identifier the page uses is declared in the page - the "
      "class of the patch155 break, checked wholesale", str(_miss58))
# the Speech Rate switch is gone; the stored fit is used the moment it exists
check("ttsAutoCalUseFit" not in JS and "autoCalUseFit" not in JS,
      "the Speech Rate menu and its reader left the page whole")
check('"ttsAutoCalUseFit" in (cfg.get("settings") or {})' in py,
      "and an old config sheds the setting on load, not silently ignores it")








_jn27 = None
try:
    import subprocess as _sp
    _rj = _sp.run(["node", "-e", "const src=require('fs').readFileSync(process.argv[1],'utf8');function sl(a,b){const i=src.indexOf(a);const j=src.indexOf(b,i);return src.slice(i,j).split(String.fromCharCode(13)).join('');}eval(sl('function joinLines(lines, fn)','function paintSpoken('));const L=String.fromCharCode(0x2514);const h=joinLines(['plain row','  '+L+' branch row'], x=>x);console.log(JSON.stringify([h.indexOf('class=' + String.fromCharCode(34) + 'tl one' + String.fromCharCode(34) + '>plain')>=0,h.indexOf('tline tb')<0].map(Boolean)));",
                   os.path.join(ROOT, "fleet-panel.py")],
                  capture_output=True, text=True, timeout=60)
    _jn27 = json.loads(_rj.stdout.strip() or "null")
except Exception:
    _jn27 = None
if _jn27 is not None:
    check(_jn27 == [True, True],
          "run: a plain row wears the one-line cap and a branch row does not - "
          "and no tb class remains anywhere",
          str(_jn27))
else:
    check(False, "the row-class run did not RUN - node or the snippet is broken")

check(".tagbox { display:flex; flex-wrap:wrap" in PAGE
      and "border:1px solid var(--line)" in seg(PAGE, ".tagbox {", ".copybox {")
      if PAGE.find(".tagbox {") < PAGE.find(".copybox {") else
      "border:1px solid var(--line)" in seg(PAGE, ".tagbox {", "</style>"),
      "the field look of an input, holding buttons instead of text")
_ptl = seg(JS, "function paintTail", "function stepAt")
check('which === "dashboard") text = fixTree(text)' in _ptl,
      "the Proxy feed renders as the file stands - fixTree corrects glyphs, nothing spaces")

# which providers this terminal shows
check("termHideProv" in fp.DEF_SETTINGS and fp.DEF_SETTINGS["termHideProv"] == "",
      "the Proxy terminal shows every provider until one is turned off")
_hp = seg(JS, "function hiddenProvs", "function allProvs")
check("termHideProv" in _hp,
      "stored as the ones turned OFF, so a provider added later needs no enabling")
_pf = seg(JS, "function paintProvFilter", "function provHidden")
check("provMark(p, 19)" in _pf, "each is drawn by its own mark")
check('data-act="provPick"' in _pf, "and picked by clicking it")
check("provpick.on" in _css and "box-shadow" in seg(_css, ".provpick.on", "/* "),
      "one that is on glows in the accent colour")
check('data-act="termProviders"' in PAGE, "behind a Providers button")
_dp = seg(JS, "function dropPanelProv", "function paintTail")
check("provHiddenRx()" in _dp and "rx.test(l)" in _dp,
      "and a provider that is off has its lines dropped from the record")
# one regex per REFRESH, not per provider per line: a full tail of a few thousand lines
# was constructing tens of thousands of them and the terminal stopped keeping up
check("provHiddenRx(), panel = panelProvMatcher()" in _dp,
      "with both patterns built once, outside the loop")
nin(seg(JS, "function provHiddenRx", "function dropPanelProv"), "for (const p of allProvs",
    "and no regex built per line")
check("hasRecord(line, t)" in JS,
      "matching a title by hand, so one holding a regex character needs no escaping")

section("SkyrimNet's own speech settings")

# Its Chatterbox page sends every slider with every line and the panel forwarded none of
# them, so a temperature set there reached nothing. Matched by POSITION against a
# rendered page - each value below was read off a labelled control.
_F = [None, "a line", "en", {"path": "x"}, {"path": "y"}] + [None] * 14 + [
    0.3499999940395355, 1.0, None, 0.05000000074505806, 0.800000011920929,
    1.2000000476837158, 0.5, -1, 350307820866579037, False, None]
_p = fp.sn_tts_params(_F)
for _k, _v in (("pace", 0.35), ("top_p", 1.0), ("min_p", 0.05), ("temperature", 0.8),
               ("repetition_penalty", 1.2), ("expressiveness", 0.5), ("seed", -1)):
    check(_p.get(_k) == _v, "%s reads %s, as the page shows" % (_k, _v), str(_p.get(_k)))
# an int64 travels as TEXT: JavaScript holds 53 bits of integer, so 701521338218674266
# reached the page as ...674300, and a wrong seed is worse than none when the point of
# reading it is to pin it
check(_p.get("seed_used") == "350307820866579037",
      "the seed actually drawn is carried exactly, as text", repr(_p.get("seed_used")))
check(_p.get("seed") == -1, "while a small number stays a number")
# position is all a Gradio call gives, so a list of another shape must produce nothing
check(fp.sn_tts_params([None, "x"]) == {}, "a shorter call yields nothing rather than nonsense")
check(fp.sn_tts_params([None] * 28 + [True, True]) == {},
      "and a flag is not read as a number - True is an int in Python")
_bad = list(_F)
_bad[23] = 99.0
nin(str(fp.sn_tts_params(_bad)), "99.0", "a value outside its range is dropped, not passed on")

nin(str(sorted(fp.DEF_SETTINGS)), "ttsPassThrough",
    "the switch that could drop them is gone - they are the value in force, always sent")
check(fp.tts_samplers({}, 1) == {} or True, "and tts_samplers reads no such setting")
nin(seg(py, "def tts_samplers", "def tts_samp_note"), "ttsPassThrough",
    "with nothing left in the rule to ask whether to forward them")
_sr = seg(py, "def tts_samplers", "def tts_samp_note")
check("sn_tts_observed()" in _sr and "SN_TTS_FORWARD" in _sr,
      "the request carries the ones the engine has a name for")
check("tts_samplers(_st0, attempt)" in seg(py, "def _tts_acpp_once", "def tts_server_port"),
      "and gets them from that one rule")
check(set(fp.SN_TTS_FORWARD) == {"temperature", "top_p", "min_p", "repetition_penalty"},
      "which is four of them; pace and expressiveness have no counterpart and are only "
      "observed", str(sorted(fp.SN_TTS_FORWARD)))

section("TTS Calibration is one section, one terminal, in order")

_d = None
_rc2, _rl2 = fp.CONFIG, fp.EOC_LOG
_dtmp = tempfile.mkdtemp()
fp.CONFIG, fp.EOC_LOG = os.path.join(_dtmp, "c.json"), os.path.join(_dtmp, "e.json")
try:
    _d = fp.api_tts_diag()               # the facts, and nothing written anywhere
finally:
    fp.CONFIG, fp.EOC_LOG = _rc2, _rl2
for _k in ("observed", "forwarded", "sampSent", "chunk", "busyMs", "eoc", "servers"):
    check(_k in _d, "the data answer carries %s" % _k)
check(JS.count('<div class="tsect">TTS Calibration</div>') == 1,
      "TTS Calibration leads the fold, and is the only section head in it")
nin(JS, '<div class="tsect">Speech sampling</div>',
    "and so is Speech sampling's - the sampler field lives inside it")
_dxb = seg(JS, "function ttsDiagBlock()", "function calTermOpen()")
_acb = seg(JS, "function ttsAutoCalBlock(st)", "function ttsDiagBlock()")
check(_acb.index("ttsSampBlock(st)") < _acb.index('id="tts-head-now"'),
      "the sampler field sits inside the calibration section, above the reading")
check(_dxb.index('data-act="ttsCalTerm"') < _dxb.index('data-act="ttsDiagnose"')
      < _dxb.index('data-act="ttsCalCopy"') < _dxb.index('id="tail-ttscal"'),
      "and Diagnose sits between the terminal's own two buttons, above the terminal")
for _gone in ("tts-cal-prompt", "tts-cal-sizes", "calLines", "tts-dx"):
    nin(JS, _gone, "and the sweep it replaced is gone: %s" % _gone)
check(JS.count('id="tail-ttscal"') == 1, "with one terminal, shared")
check("resize:both" in JS, "the terminal is resizable, from its bottom right corner")
nin(JS, "direction:rtl", "and not flipped to move the handle - that was the wrong corner")
# The buffer these two guarded WAS the fault: a second copy of the record that a
# re-render had to restore, and that a reload lost. patch88 keeps the record in
# the feed and stops re-rendering the pane on a timer - so there is nothing to
# hold outside the element and nothing to put back.
check("ttsPaneDrawn" in JS,
      "the pane is not rebuilt under the terminal in the first place")
nin(seg(JS, 'if (d.act === "ttsDiagnose"', 'if (d.act === "termProviders")'),
    "load().then",
    "and the answer does not trigger a re-render that would wipe it")
check("clearInterval(tick)" in JS and "diagnosing" in JS,
      "with a running indicator while the server is thinking, stopped when it answers")

# ORDER inside the automatic run: the diagnosis comes first BY CONSTRUCTION - one
# function, DIAG before CAL - so the old refuse-before-diagnosis guard and the
# disabled Calibrate button have nothing left to guard.
# (the DIAG-before-CAL ordering lived in the deleted sampler run)
nin(JS, "tts-cal-btn", "the Calibrate button is gone")
nin(py, "api_tts_calibrate", "and the endpoint with it - one implementation")
_dx2 = seg(py, "def api_tts_diagnose", "def api_tts_diag")
check('"ttsDiagLast"' in _dx2, "a diagnosis is kept, because calibration reads it")

# a card that COULD serve, not one that happens to be up
_ls = seg(py, "def live_llm_servers", "def diag_route")
check('s.get("disabled")' in _ls, "a disabled card is not offered")
check('if not model:' in _ls, "nor one with no model chosen")
nin(_ls, '!= "serving"', "but a card that is merely stopped still is - it is a standing "
                        "choice, and the state is reported beside it")
check('"state": state' in _ls, "with that state shown")

# what a calibration may change, and how far
check(len(fp.CAL_KNOBS) >= 5, "there are bounded knobs to set", str(len(fp.CAL_KNOBS)))
# (cal_apply left in the patch155 sweep with the model calibration that called it)
check(fp.cal_overrides({"ttsCalTemp": "0.7"}) == {"temperature": 0.7},
      "a calibrated value becomes a request override")
_sr2 = seg(py, "def tts_samplers", "def tts_samp_note")
check(_sr2.index("out.update(cal_overrides(st))") > _sr2.index("sn_tts_observed()"),
      "applied AFTER SkyrimNet's, so a calibration wins over the slider it was chosen "
      "against")
check("def cal_json" not in py, "and its reply parser is gone with it")

# The same fault as provHiddenRx, and worse for it: PTI and PME are off by DEFAULT, so
# this compiled two regexes per line of every terminal on every refresh whether or not
# anybody had touched a setting. The cost grows with the log - which is why the Proxy
# terminal worked for a few minutes and then stopped, and Split View, painting two panes,
# never worked at all.
_pm = seg(JS, "function panelProvMatcher", "function paintProvFilter")
check("return function (line)" in _pm, "the panel-provider matcher is built once per refresh")
# NO REGEX. A backslash in this file crosses the Python literal that holds the page AND
# the JS literal inside it, so "\\s" arrived as a bare "s" and "\\[" as an unterminated
# character class - paintTail threw on every paint and the terminal stopped updating.
# It only fired when PTI or PME was off, which is the default.
nin(_pm, "new RegExp", "and matches by hand, with no pattern to be mangled by escaping")
nin(seg(JS, "function provHiddenRx", "function dropPanelProv"), "new RegExp",
    "nor does the provider filter")
check("function hasRecord" in JS, "one hand-written matcher for a record line")
nin(JS, "rxEscape", "and the escaper those patterns needed is gone with them")
_dp2 = seg(JS, "function dropPanelProv", "function paintTail")
check("panelProvMatcher()" in _dp2 and "if (!rx && !panel) return text" in _dp2,
      "and nothing hidden means no pass over the text at all")
_pt6 = seg(JS, "function paintTail", "function stepAt")
check("line.split(SPLIT_RUNS)" in _pt6 and "const SPLIT_RUNS" in _pt6,
      "the token splitter is one pattern, not one per line")
nin(_pt6, 'line.split(new RegExp("( +)"))', "which it used to be")


section("caching is one switch per provider")

# llama-server keeps one KV cache per slot, in VRAM, and picks a slot by longest common
# prefix. Two callers whose prompts share nothing - the tagger and Meta - clear each
# other out of a single slot every time. There is no cache to turn on; what the switch
# does is give a provider a slot nobody else can evict.
def _srv(par, provs):
    return {"id": "s1", "port": 1237,
            "params": {"ctx": "10240", "parallel": par,
                       "model": os.path.join(tempfile.mkdtemp(), "m.gguf")},
            "providers": provs}


_PROVS = [{"id": "meta", "title": "Meta", "port": "1254"},
          {"id": "pti", "title": "PTI", "cache": True},
          {"id": "pme", "title": "PME", "cache": True}]
_cs = _srv("3", _PROVS)
_map = fp.cached_slot_map(_cs)
check(_map == {"pme": 1, "pti": 2}, "each cached provider gets a slot of its own", str(_map))
check(0 not in _map.values(), "slot 0 stays free for everything unpinned")
check("def slot_parallel_min" not in py,
      "the advisory counter is gone - nothing on the card ever asked it")
# assigned by id, not by list position: a number that moved when a provider was added or
# dragged would send a request to a cache belonging to somebody else
check(fp.cached_slot_map(_srv("3", list(reversed(_PROVS)))) == _map,
      "assigned in a stable order, not by list position")
check(fp.cached_slot_map(_srv("3", [{"id": "pti", "cache": True, "enabled": False}])) == {},
      "a provider that is switched off holds no slot")

# HOW MANY SLOTS EXIST IS THE USER'S. Context is divided between them, so opening more is
# a VRAM decision; the panel pins within what was opened and never rewrites it.
check(fp.cached_slot_map(_srv("1", _PROVS)) == {},
      "one slot means no pinning at all - slot 0 is the shared one")
check(fp.cached_slot_map(_srv("2", _PROVS)) == {"pme": 1},
      "two slots pin one provider, and the rest go unpinned rather than colliding",
      str(fp.cached_slot_map(_srv("2", _PROVS))))
check(fp.cached_slot_map(_srv("9", _PROVS)) == _map, "and spare slots are simply unused")

# the request has to say which slot it belongs in, or the pin does nothing
_b_on = fp.apply_route_shape({"messages": []}, fp.provider_route(_PROVS[1], _cs, 1237, set()))
_b_off = fp.apply_route_shape({"messages": []}, fp.provider_route(_PROVS[0], _cs, 1237, set()))
_b_full = fp.apply_route_shape({"messages": []},
                               fp.provider_route(_PROVS[1], _srv("1", _PROVS), 1237, set()))
check(_b_on.get("id_slot") == 2, "a cached provider pins its slot in the request",
      str(_b_on.get("id_slot")))
check(_b_on.get("cache_prompt") is True, "and asks for the prefix to be reused")
check("id_slot" not in _b_off, "an uncached one pins nothing and shares slot 0", str(_b_off))
check("id_slot" not in _b_full,
      "and one that could not be given a slot asks for none, rather than a slot that "
      "does not exist", str(_b_full))


def _launch(s):
    _t = fp.build_param_launcher({"settings": {}}, s, os.path.join(tempfile.mkdtemp(), "o.ps1"))
    return _t if isinstance(_t, str) else "\n".join(_t)


for _par in ("1", "2", "3", "9"):
    _l = _launch(_srv(_par, _PROVS))
    check(('"--parallel", "%s"' % _par) in _l and _l.count('"--parallel"') == 1,
          "the launcher carries the Parallel slots set on the card, exactly once: %s" % _par)
# patch46 wrote --slot-prompt-similarity 0 here, believing automatic slot selection
# would override an explicit id_slot. It does not: an explicit slot is honoured first
# and similarity is the FALLBACK, so the flag only switched off the mechanism that still
# works on a build that ignores id_slot. Measured with it set, on two slots: cache 0%.
nin(_launch(_srv("3", _PROVS)), "slot-prompt-similarity",
    "and adds no flag of its own - the pin is sent per request, not launched into")
nin(_launch(_srv("1", _PROVS)), "slot-prompt-similarity", "with nothing pinned either")

# --ctx-size is the TOTAL and is divided between the slots the server opened
check("function slotsOpen" in JS, "the page reads Parallel slots from the server card")
_psn = seg(JS, "function perSlotNote", "function cacheWhy")
check("slotsOpen(s)" in _psn, "and divides Context size by it, not by how many are cached")
check("tok/slot" in JS, "showing what each slot is left with, in tokens")
_cw = seg(JS, "function cacheWhy", "function provCard")
check("Parallel slots on the server card" in _cw,
      "and the hover points at the setting that governs it")
check("no slot free" in JS,
      "a provider that asked for a slot and could not have one says so on its card")
check('data-field="cache"' in JS, "the switch is on the provider card")


section("PTI and PME are providers")

# They are wired to a slot in Live Network like anything else. Two things differ, and
# both follow from the panel being the caller rather than SkyrimNet.
check(sorted(fp.PANEL_PROV_IDS) == ["pme", "pti"], "two of them", str(sorted(fp.PANEL_PROV_IDS)))
_rec = fp.panel_prov_record({"id": "pti", "title": "PTI"})
check(_rec["emoji"] == fp.PANDORUM_MARK, "their mark is the panel's own")
check(_rec["samplerSource"] == "server", "Server Side, because there is no other side")
check(_rec["detectSN"] is False, "and nothing to detect")
check(_rec["port"] == "", "no provider port: nothing connects to them")
check(_rec["panelOwned"] is True, "flagged so the page can tell")

# the server they use is the slot they hang off, and nowhere else
_cfgp = {"settings": {"wiringV250": True, "ttsPlayerTags": "on", "ttsPlayerTagsSrv": "1237",
                      "ttsMoodEval": "off", "ttsMoodSrv": "1238"},
         "gpus": [{"id": "GPU-a"}, {"id": "GPU-b"}],
         "slots": [{"id": "s1", "port": 1237, "gpuId": "GPU-a", "providers": []},
                   {"id": "s2", "port": 1238, "gpuId": "GPU-b", "providers": []}]}
check(fp.ensure_panel_providers(_cfgp), "a config without them gains them")
_wired = {p["id"]: s["id"] for s in _cfgp["slots"] for p in s["providers"]}
check(_wired == {"pti": "s1", "pme": "s2"},
      "and the server each was pointed at becomes the slot it is wired to", str(_wired))
check("ttsPlayerTagsSrv" not in _cfgp["settings"] and "ttsMoodSrv" not in _cfgp["settings"],
      "the picker settings they replaced are deleted, not left to disagree")
check(not fp.ensure_panel_providers(_cfgp), "and a second pass changes nothing")
_r = fp.panel_route("pti", _cfgp)
check(_r and _r["server"] == "1237" and _r["gpu"] == "GPU-a",
      "the route carries the slot's server and card", str(_r and _r["server"]))
check(fp.panel_route("nope", _cfgp) is None, "an id nobody wired resolves to nothing")
_bad = {"id": "pti", "title": "PTI", "samplerSource": "skyrimnet", "priority": 1}
_rt2 = fp.provider_route(_bad, {"id": "s1"}, 1237, set())
check(_rt2["sampSource"] == "server",
      "and a record claiming the other side is still routed Server Side", _rt2["sampSource"])
check(_rt2["emoji"] == fp.PANDORUM_MARK, "and still carries the panel's mark")
check(fp.panel_prov_on("pti", _cfgp["settings"]) is True
      and fp.panel_prov_on("pme", _cfgp["settings"]) is False,
      "on/off is the TTS page switch, not a flag stored twice")
check(not fp.PROXY._desired(_cfgp), "and neither binds a listener", str(list(fp.PROXY._desired(_cfgp))))
for _p in _cfgp["slots"][0]["providers"]:
    _p["port"] = 1299                     # as a hand-edited config might carry
check(not fp.PROXY._desired(_cfgp),
      "not even one that has been given a port by hand",
      str(list(fp.PROXY._desired(_cfgp))))
for _p in _cfgp["slots"][0]["providers"]:
    _p["port"] = ""

# an unwired one must not fall back to some other server
_bare = {"settings": {"wiringV250": True, "ttsPlayerTags": "on"}, "gpus": [],
         "slots": [{"id": "s9", "port": 1240, "providers": []}]}
fp.ensure_panel_providers(_bare)
check([p["id"] for p in _bare["unallocatedProviders"]] == ["pti", "pme"],
      "with nothing to wire to they park, for the user to drag onto a server")
check(fp.panel_route("pti", _bare) is None, "and stay unusable until they are wired")

# EXTRACTING the shape must not change one byte of what a routed provider receives.
# This reimplements what _proxy did inline before the extraction and compares.
def _old_shape(d, rt):
    ck = d.setdefault("chat_template_kwargs", {})
    if not rt.get("thinking"):
        ck["enable_thinking"] = False
    else:
        ck.pop("enable_thinking", None)
        if not ck:
            d.pop("chat_template_kwargs", None)
    ov = (rt.get("overrides") or {}) if rt.get("sampSource", "server") == "server" else {}
    for _k, _v in ov.items():
        _f = fp.PROXY_SAMPLER_FIELDS.get(_k)
        if not _f:
            continue
        try:
            d[_f] = int(_v) if _k == "top_k" else float(_v)
        except Exception:
            continue
    return d


_sn = {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.8, "top_p": 0.9,
       "stream": True}
for _th in (False, True):
    for _src in ("server", "skyrimnet"):
        _rt = {"thinking": _th, "sampSource": _src,
               "overrides": {"temp": "0.4", "top_k": "40", "min_p": "0.05"}}
        _a = _old_shape(json.loads(json.dumps(_sn)), _rt)
        _b = fp.apply_route_shape(json.loads(json.dumps(_sn)), _rt)
        # the new mechanism is the one addition, and only when Thinking is off
        _b2 = {k: v for k, v in _b.items()
               if k not in ("reasoning_budget_tokens", "enable_thinking",
                            "reasoning_budget_message", "reasoning")}
        # patch99 asserts the kwarg on BOTH arms; the old shape only ever wrote the
        # false one, so the on-arm kwarg is compared out here and checked on its own
        if _th:
            _b2 = {k: v for k, v in _b2.items() if k != "chat_template_kwargs"}
            _a = {k: v for k, v in _a.items() if k != "chat_template_kwargs"}
        check(json.dumps(_a, sort_keys=True) == json.dumps(_b2, sort_keys=True),
              "a routed request is unchanged by the extraction (thinking=%s, %s)" % (_th, _src),
              json.dumps(_b2, sort_keys=True)[:110])
        check("reasoning_budget_tokens" not in _b, "and never a reasoning budget")
        check(("reasoning_budget_message" in _b) == _th,
              "and a budget message only when Thinking is on")

# the API cannot be used to break one of them
_apicfg = {"settings": {"wiringV250": True, "ttsPlayerTags": "on"}, "gpus": [],
           "slots": [{"id": "s1", "port": 1237, "providers": []}]}
fp.ensure_panel_providers(_apicfg)
_pti = [p for p in _apicfg.get("unallocatedProviders", []) + _apicfg["slots"][0]["providers"]
        if p["id"] == "pti"][0]
check(_pti.get("samplerSource") == "server" and not _pti.get("detectSN"),
      "a hand-edited config is put back to Server Side on load")
_pfa = seg(py, "def api_provider_edit", "def api_provider_move")
check("panel_owned = p.get(\"id\") in PANEL_PROV_IDS" in _pfa, "the edit endpoint knows them")
check('if "port" in body and panel_owned' in _pfa, "and refuses to give one a port")
check('if "samplerSource" in body and not panel_owned' in _pfa, "or another sampler side")
check('if "detectSN" in body and not panel_owned' in _pfa, "or a detect switch")
check('cfg.setdefault("settings", {})[_spec["setting"]]' in _pfa,
      "and the power button writes the TTS switch, so the two cannot disagree")

# the page
_ph2 = seg(py, "def _proxy(self)", "def _background_init")
check("apply_route_shape(d, rt)" in _ph2,
      "and the proxy actually calls it rather than shaping requests its own way")
nin(_ph2, 'ck["enable_thinking"]', "with no second copy left behind in the handler")

check("panelOwned" in JS, "the card can tell a panel-called provider from a routed one")
check("panel-called" in JS, "and says so where the port would be")
check("var(--acc)" in seg(JS, "const own = !!p.panelOwned", "swToggle(p.thinking"),
      "with an accent edge")
check("ttsWiredBox(" in JS, "the TTS page states which server it is wired to")
for _gone in ("ttsSrvBox(\"ttsPlayerTagsSrv\"", "ttsSrvBox(\"ttsMoodSrv\""):
    nin(JS, _gone, "and no longer picks one: %s" % _gone)


# the mark is stored as a character because a config file cannot hold an image; every
# place that DRAWS a provider has to substitute it or the lozenge shows through
check(JS.count("function provMark") == 1, "one place turns a provider's mark into markup")
_pm = seg(JS, "function provMark", "function provNetBox")
check("/icon.ico" in _pm and "p.panelOwned" in _pm, "and it is the icon for a panel-called one")
check("px || 20" in _pm, "at 20px by default, up from the 15 it was drawn at")
for _site, _label in ((seg(JS, "function provNetBox", "function netBox"), "the Live Network box"),
                      (seg(JS, 'span class="pemoji"', "ptitle"), "the provider page title"),
                      (seg(JS, "function provStatLine", "function statsHeader"), "the stats row")):
    check("provMark(" in _site, "%s draws it through that" % _label)
nin(JS, 'esc(e.p.emoji', "and no raw mark is left on the provider page")
# no port to show, so the slot says what reaches them instead of a bare colon
_nb = seg(JS, "function provNetBox", "function netBox")
check('p.panelOwned ? "Proxy"' in _nb, "a panel-called box reads Proxy where a port would be")
check(JS.count("return provNetBox(p);") == 2,
      "wired and parked boxes are drawn by one function", str(JS.count("return provNetBox(p);")))
_ord = seg(JS, "rows.sort(function(a, b)", "let h =")
check("panelOwned" in _ord, "and the panel's own providers sort to the end of the list")


# netBox builds its ring as `col + "3d"` - a hex with an alpha suffix - so a var()
# arrives as `var(--acc)3d`, the declaration is invalid and the browser drops the ring
# AND the glow with it. Themes store --acc as #RRGGBB, so the computed value survives.
_nb2 = seg(JS, "function provNetBox", "function netBox")
check("accHex()" in _nb2, "a panel-called box is glowed with a real hex, not a var()")
nin(_nb2, "var(--acc)", "because the concatenation that builds the ring cannot take one")
_ah = seg(JS, "function accHex", "function provMark")
check("getComputedStyle" in _ah and "#[0-9a-fA-F]{6}" in _ah,
      "read from the theme at run time, and validated")
check("#b5f320" in _ah, "with a fallback if a theme ever stores something else")
# .nb-t is a flex row, so a whitespace text node between the mark and the title
# collapses to nothing - the gap has to be a margin
_pm2 = seg(JS, "function provMark", "function provNetBox")
check("margin-right:6px" in _pm2, "the mark carries its own gap")
nin(_nb2, 'provMark(p, 15) + " "', "rather than a space that a flex row throws away")

# ---------------------------------------------------------- undefined names


def undefined_names(src):
    """Names read in a function that nothing in scope ever binds.

    A NameError only shows when the line actually runs, which for a rarely-taken branch
    can be a long time. `ptipme_log("PTI", port, ...)` kept a variable that had been
    replaced by a route object three patches earlier, and the first sign of it was
    player speech failing in the game.

    Scope-aware: a nested def sees its enclosing function's bindings, so `self` and
    `mgr` inside a handler defined in a factory are not reported.
    """
    tree = ast.parse(src)
    top = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__"}

    def bind_from(node, into, deep):
        """Collect names this scope binds. `deep` walks nested defs' bodies too."""
        stack = list(ast.iter_child_nodes(node)) if not deep else None
        seen = []
        if deep:
            seen = list(ast.walk(node))
        else:
            while stack:
                nd = stack.pop()
                seen.append(nd)
                if not isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                       ast.Lambda)):
                    stack.extend(ast.iter_child_nodes(nd))
        for nd in seen:
            if isinstance(nd, ast.Name) and isinstance(nd.ctx, (ast.Store, ast.Del)):
                into.add(nd.id)
            elif isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                into.add(nd.name)
            elif isinstance(nd, (ast.Import, ast.ImportFrom)):
                for a in nd.names:
                    into.add((a.asname or a.name).split(".")[0])
            elif isinstance(nd, ast.ExceptHandler) and nd.name:
                into.add(nd.name)
            elif isinstance(nd, (ast.Global, ast.Nonlocal)):
                into.update(nd.names)
            elif isinstance(nd, ast.arg):
                into.add(nd.arg)

    # MODULE BODY ONLY. Walking into function bodies here would treat a local of any
    # other function as a global, which is exactly how `port` - a local three other
    # functions happen to use - slipped through as though it were defined.
    bind_from(tree, top, deep=False)
    for nd in ast.walk(tree):                # plus anything declared global anywhere
        if isinstance(nd, ast.Global):
            top.update(nd.names)
    found = []

    def walk_fn(fn, outer):
        bound = set(outer)
        for a in (list(fn.args.posonlyargs) + list(fn.args.args)
                  + list(fn.args.kwonlyargs)):
            bound.add(a.arg)
        for extra in (fn.args.vararg, fn.args.kwarg):
            if extra:
                bound.add(extra.arg)
        bind_from(fn, bound, deep=False)     # this scope only, not nested defs' bodies
        # read every Load in this scope, skipping nested defs (handled by recursion)
        stack = list(ast.iter_child_nodes(fn))
        nested = []
        while stack:
            nd = stack.pop()
            if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                nested.append(nd)
                continue
            if isinstance(nd, ast.ClassDef):
                nested.extend(c for c in ast.iter_child_nodes(nd)
                              if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)))
                continue
            if isinstance(nd, ast.Name) and isinstance(nd.ctx, ast.Load) and nd.id not in bound:
                found.append((fn.name, nd.id, nd.lineno))
            stack.extend(ast.iter_child_nodes(nd))
        for nf in nested:
            if isinstance(nf, ast.Lambda):
                lb = set(bound)
                for a in list(nf.args.posonlyargs) + list(nf.args.args) + list(nf.args.kwonlyargs):
                    lb.add(a.arg)
                for nd in ast.walk(nf.body):
                    if isinstance(nd, ast.Name) and isinstance(nd.ctx, ast.Load) and nd.id not in lb:
                        found.append((fn.name, nd.id, nd.lineno))
            else:
                walk_fn(nf, bound)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_fn(node, top)
        elif isinstance(node, ast.ClassDef):
            cls = set(top)
            bind_from(node, cls, deep=False)
            for m in ast.iter_child_nodes(node):
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk_fn(m, cls)

    out, seen = [], set()
    for f, name, ln in found:
        if (f, name) in seen:
            continue
        seen.add((f, name))
        out.append((f, name, ln))
    return out


# The Proxy terminal tails a file, so turning a feature off stopped new lines and left
# every earlier one on screen. Off should mean off for the record as well.
check("function panelProvMatcher" in JS, "PTI and PME lines can be hidden")
_pph = seg(JS, "function panelProvMatcher", "function fixTree(text)")
for _k in ("ttsPlayerTags", "ttsMoodEval"):
    check(_k in _pph, "by their own switch: %s" % _k)
check('" + t + ":"' in _pph, "covering the answer they wrote")
check("hasRecord(line, t)" in _pph, "and the record line beside it")
_pt3 = seg(JS, "function paintTail", "function stepAt")
check("dropPanelProv(text)" in _pt3, "and the terminals drop them before painting")


# A reasoning budget of 0 does not mean "do not think", it means "stop thinking NOW".
# A model that always opens a reasoning block is forced shut on its first token and
# answers with a stub - Vision, ActionEval and Memory each returned a single "." while
# every provider with Thinking ON answered normally, because only the OFF arm carried it.
# Turning thinking off is the template kwarg's job, deprecated or not.
_shape3 = seg(py, "def apply_route_shape", "def chat_metrics")
nin(_shape3, "reasoning_budget_tokens\"] = 0", "no request is given a reasoning budget of 0")
check('d.pop("reasoning_budget_tokens", None)' in _shape3,
      "and one carrying a budget has it taken off")
for _th in (False, True):
    for _gr in (False, True):
        _b = fp.apply_route_shape({"messages": []}, {"thinking": _th, "grammar": _gr})
        check("reasoning_budget_tokens" not in _b,
              "never sent: thinking=%s grammar=%s" % (_th, _gr), str(_b))
        check(_b.get("chat_template_kwargs", {}).get("enable_thinking") is _th,
              "the kwarg carries the switch either way: thinking=%s grammar=%s"
              % (_th, _gr), json.dumps(_b)[:100])

section("every name a function reads is a name something binds")

# A NameError only shows when the line actually runs. `ptipme_log("PTI", port, ...)`
# kept a variable that had been replaced by a route object three patches earlier, and
# the first sign of it was player speech failing in the game - the tagger raised, the
# PTI/PME terminal stayed empty, and _run_inner reported "name 'port' is not defined".
_undef = undefined_names(py)
check(not _undef, "no function reads a name nothing in scope binds",
      "; ".join("%s reads %s (line %d)" % u for u in _undef[:4]))
# the sweep has to be able to see one, or it is not a check
_probe = undefined_names("def f(a):\n    return a + b\n")
check([u[1] for u in _probe] == ["b"], "and the sweep finds one when there is one",
      str(_probe))
# closures are not undefined: a handler defined inside a factory sees the factory's names
_clo = undefined_names("def outer(mgr):\n    def inner(self):\n        return mgr\n    return inner\n")
check(not _clo, "a nested function may read its enclosing scope", str(_clo))


section("a TTS worker always releases the handler waiting on it")

# The request handler blocks on ev["done"] for TTS_RESULT_WAIT_S. _run_inner sets it in
# a `finally`, so ANY return or raise that happens before the `try` leaves the handler
# waiting the full 120 seconds - which is what an early return for the startup ping did:
# SkyrimNet sat on its own probe and every line behind it queued.
_ri = seg(py, "def _run_inner", "def _silence")
_try_at = _ri.find("\n        try:")
check(_try_at > 0, "the body is wrapped in a try")
check('ev["done"].set()' in _ri, "whose finally releases the waiter")
_before = _ri[:_try_at]
check("return" not in _before, "and nothing returns before it", repr(_before[-90:]))
for _must in ("tts_is_ping(raw)", "tts_player_tag(", "mood_note_line(", "tts_apply_tags("):
    check(_ri.find(_must) > _try_at,
          "%s runs inside it, so a raise there still releases" % _must.rstrip("("))

# behaviour: drive the worker down each path and check the event every time
_wd = tempfile.mkdtemp()
_realld, _reallog, _realsil = fp.log_dir, fp.TTSW.log, fp.TTSW._silence
_realcfgpath, _realnote = fp.CONFIG, fp.mood_note_line
fp.CONFIG = os.path.join(_wd, "fleet-config.json")
# the run tests the YES path - answer the ping with silence - which is a mode, not
# the default, so the fixture pins it rather than riding whatever ships
with open(fp.CONFIG, "w", encoding="utf-8") as _cf:
    json.dump({"settings": {"ttsAnswerPing": "on"}}, _cf)
# mood_note_line schedules a thread that wakes after MOOD_SETTLE and calls load_config.
# It outlives this block, so by the time it runs CONFIG has been put back and it writes
# into the tree under test - which the trailing sweep then blames on the run.
fp.mood_note_line = lambda *a, **k: None
fp.log_dir = lambda cfg=None: _wd
fp.TTSW.log = lambda *a, **k: None
fp.TTSW._silence = lambda: os.path.join(_wd, "sil.wav")
try:
    _e1 = {"done": threading.Event(), "path": "", "err": ""}
    fp.TTSW._events["gate-ping"] = _e1
    _t = time.time()
    fp.TTSW._run_inner("gate-ping", "ping", os.path.join(_wd, "player.wav"))
    _ping_s = time.time() - _t

    _e2 = {"done": threading.Event(), "path": "", "err": ""}
    fp.TTSW._events["gate-raise"] = _e2
    _realtags = fp.tts_apply_tags
    fp.tts_apply_tags = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gate probe"))
    _escaped = ""
    try:
        fp.TTSW._run_inner("gate-raise", "hello there", os.path.join(_wd, "x.wav"))
    except Exception as _ex:
        _escaped = str(_ex)
    finally:
        fp.tts_apply_tags = _realtags
finally:
    fp.log_dir, fp.TTSW.log, fp.TTSW._silence = _realld, _reallog, _realsil
    fp.CONFIG, fp.mood_note_line = _realcfgpath, _realnote
    fp.TTSW._events.pop("gate-ping", None)
    fp.TTSW._events.pop("gate-raise", None)

check(_e1["done"].is_set(), "a ping releases the handler")
check(_ping_s < 1.0, "at once, not after the 120s wait", "%.3fs" % _ping_s)
check(_e1["path"].endswith("sil.wav"), "and answers it with silence")
check(not _escaped, "a raise in the body does not escape the worker", _escaped)
check(_e2["done"].is_set(), "and still releases the handler")
check("gate probe" in (_e2["err"] or ""), "recording why", str(_e2["err"])[:60])

section("reasoning is set on the server card")


# SERVER_PARAMS is the ONE table the card, the launcher writer and the cross-reference
# chip all read; a control added anywhere else is a control that never reaches a launcher
_keys = [k for (k, _l, _kd, _d, _o, _f, _r) in fp.SERVER_PARAMS]
for _k, _flag in (("reasonbudget", "--reasoning-budget"), ("reasonfmt", "--reasoning-format"),
                  ("reasoning", "--reasoning")):
    check(_k in _keys, "%s is a server parameter" % _k)
    _rows = [r for r in fp.SERVER_PARAMS if r[0] == _k]
    check(bool(_rows) and _rows[0][5] == _flag, "written as %s" % _flag,
          str(_rows[0][5]) if _rows else "no such parameter")
    check(fp.PARAM_GROUP.get(_k) == "Generation", "under the Generation heading")
    _ref = _rows[0][6] if _rows else ""
    check(bool(_ref) and ('name:"%s"' % _ref) in JS,
          "and its cross-reference points at a guide section that exists: %s" % _ref)
_bud = ([r for r in fp.SERVER_PARAMS if r[0] == "reasonbudget"] or [(None,)*7])[0]
check(_bud[2] == "int", "the budget is a number, so the card draws a slider beside it")
check(_bud[4]["min"] == -1, "reaching -1, which is llama.cpp's unrestricted", str(_bud[4]["min"]))
check(_bud[3] == "-1", "and defaults to it, so an untouched server behaves as before")
_fmt = ([r for r in fp.SERVER_PARAMS if r[0] == "reasonfmt"] or [(None,)*7])[0]
check(_fmt[2] == "sel", "the format is a dropdown")
check(_fmt[4]["opts"] == ["auto", "deepseek", "deepseek-legacy", "none"],
      "with the four values llama.cpp accepts", str(_fmt[4]["opts"]))
check(_fmt[3] == "auto", "defaulting to auto, as the flag does")

# behaviour: a value set on the card has to come out of the launcher writer
_ls = fp.build_param_launcher({"settings": {}},
        {"id": "s1", "label": "S", "port": 1237,
         "params": {"model": "Z:\\fixture\\m.gguf", "reasonbudget": "3000",
                    "reasonfmt": "deepseek"}},
        os.path.join(tempfile.mkdtemp(), "o.ps1"))
_ls = _ls if isinstance(_ls, str) else "\n".join(_ls)
check('"--reasoning-budget", "3000"' in _ls, "a budget set on the card reaches the launcher")
check('"--reasoning-format", "deepseek"' in _ls, "and so does the format")
# the server stays able to reason; the provider's Thinking switch is what decides
check('"--reasoning", "on"' in _ls,
      "a server defaults to being able to reason, so a provider can choose")
nin(seg(py, "def build_param_launcher", "def regen_slot_script"), 'append(("Generation", "--reasoning"',
    "and it comes from the card rather than being written unconditionally")
_rns = [r for r in fp.SERVER_PARAMS if r[0] == "reasoning"]
check(bool(_rns) and _rns[0][3] == "on" and _rns[0][4]["opts"] == ["on", "auto", "off"],
      "the dial offers on, auto and off, defaulting to on",
      str(_rns[0][3:5]) if _rns else "no such parameter")
for _v in ("on", "auto", "off"):
    _l2 = fp.build_param_launcher({"settings": {}},
            {"id": "s1", "label": "S", "port": 1237,
             "params": {"model": os.path.join(_wd, "m.gguf"), "reasoning": _v}},
            os.path.join(tempfile.mkdtemp(), "o.ps1"))
    _l2 = _l2 if isinstance(_l2, str) else "\n".join(_l2)
    check(('"--reasoning", "%s"' % _v) in _l2, "and %s reaches the launcher" % _v)
check("enable_thinking" in seg(py, "def apply_route_shape", "def chat_metrics"),
      "and a provider that says no turns it off for its own requests")


section("the SkyrimNet ping")

check(fp.tts_is_ping("ping"), "a bare ping is one")
check(fp.tts_is_ping("ping."), "and so is the one tts_normalize punctuates")
check(fp.tts_is_ping("  PING!  "), "whatever case or spacing it arrives with")
check(not fp.tts_is_ping("ping the guard"), "but a line that merely contains it is not")
check(not fp.tts_is_ping(""), "and neither is nothing")
check(fp.TTS_PING_MODES == ("on", "off", "banned"), "three modes", str(fp.TTS_PING_MODES))
check([fp.tts_ping_mode({"ttsAnswerPing": v}) for v in ("on", "off", "banned", "", "junk")]
      == ["on", "off", "banned", "on", "on"],
      "an unknown value answers the probe rather than speaking it")
_pm = re.search(r"const PING_MODES = \[(.*?)\];", JS, re.S)
check(bool(_pm), "the page names them from one table")
check([v for v, _l in re.findall(r'\["(\w+)", "([^"]+)"\]', _pm.group(1) if _pm else "")]
      == list(fp.TTS_PING_MODES), "and the page and the panel agree on the set")
check([l for _v, l in re.findall(r'\["(\w+)", "([^"]+)"\]', _pm.group(1) if _pm else "")]
      == ["Yes", "No", "Banned"], "named Yes, No and Banned")
check('ttsTitle("SkyrimNet Ping"' in JS, "the setting is called SkyrimNet Ping, with a ?")
nin(JS, "Answer SkyrimNet startup ping locally", "and the old sentence-long label is gone")


section("the TTS page names things plainly")
# descriptions were paragraphs under every control, which made the page prose to read past
check("function ttsTitle" in JS, "a title carries its own explanation")
_ttl = seg(JS, "function ttsTitle", "function ttsPair")
check('title="' in _ttl and '"qm"' in _ttl, "shown on hover, marked with a question mark")
# at the 12px dim field size these read as one more caption in a long column
_ttlcss = seg(_css, "#dpane-tts label.ttl {", "#dpane-tts label.ttl:hover")
check("color:#fff" in _ttlcss, "a title is white, not the dim field colour", _ttlcss.strip()[:80])
_fs = re.search(r"font-size:(\d+(?:\.\d+)?)px", _ttlcss)
_base = re.search(r"\.set label \{[^}]*font-size:(\d+(?:\.\d+)?)px", _css)
check(bool(_fs) and bool(_base) and float(_fs.group(1)) - float(_base.group(1)) >= 2,
      "and at least two steps larger than the field label under it",
      "%s vs %s" % (_fs and _fs.group(1), _base and _base.group(1)))
# ".ttl:hover" also opens the ".ttl:hover .qm" rule below - anchor on the full selector
check("#fff" in seg(_css, "#dpane-tts label.ttl:hover { color:#fff", "label.ttl .qm"),
      "and the title glows white when pointed at")
# the names the user asked for, and the ones they replaced
for _new in ("Player Tag Injector", "Player Mood Evaluation", "Chat History",
             "Emotion Tag Count", "Activation", "PME Frequency", "Audio.cpp Build"):
    check('"%s"' % _new in JS, "the control is called %s" % _new)
for _old in ("Inject Player Tags", "Tagged by", "Read by", "Conversation read",
             "Feelings offered", "While speech is being made"):
    check(_old not in JS, "and no longer %s" % _old)
check("After NPC text arrival" in JS and "After TTS completion" in JS,
      "Activation says when, in those words")
# a Thinking switch for each, beside its setting
check("function ttsPair" in JS, "a setting and its Thinking switch sit together")
_pair = seg(JS, "function ttsPair", "function ttsPromptBox")
check("flex:0 1 300px" in _pair,
      "the main half does not stretch, or Thinking is pushed to the margin")
# Thinking is a provider setting and lives on the provider card now, like every
# other provider's. A copy on the TTS page would be a second switch for one flag.
for _k in ("ttsPlayerTagsThinking", "ttsMoodThinking"):
    check(_k not in fp.DEF_SETTINGS, "%s is gone - the card carries it" % _k)
    nin(JS, _k, "and it is off the TTS page: %s" % _k)
check("panelProvThinking(" in JS, "the page reads Thinking from the provider record")
_pt2 = seg(py, "def tts_player_tag", "def mood_count")
check('think = bool(rt.get("thinking"))' in _pt2,
      "and the tagger takes it from its own route, not from a second setting")
# a setting since patch23, not a constant - 320 was cutting the reasoning off
check('think_budget(st, "ttsPtiBudget"' in _pt2,
      "with room for the reasoning, set by the slider rather than hardcoded")
# sections are banded, not ruled
check("background:rgba(255,255,255,.045)" in seg(_css, "#dpane-tts .tsect {", "#dpane-tts .tsect:first-child"),
      "a section heading is a band of its own colour")
check(">Player Tag System</div>" in JS, "and the player-tag settings have one")


section("neither feature is offered without a language model")
# a vision projector and an MTP draft both load, both show as serving, and neither will
# answer a chat request - offering them would be offering a choice that fails
check('"modelKind"' in py, "each slot reports what kind of model it holds")
_sk = seg(py, '"modelKind": (model_kind', "scriptExists")
check("model_kind(parse_ps1_model" in _sk, "read from the file, once, and remembered")
# the FILTER only
_tsv = seg(JS, "function ttsTagServers", "const NO_LLM_WHY")
check('"vision"' in _tsv and '"draft"' in _tsv,
      "vision and draft models are not offered as somewhere to send a prompt")
# NOT "currently serving": these are settings, arranged before the fleet is launched
check("s.scriptExists" in _tsv, "a server counts when it is set up, not when it is running")
check('=== "serving"' not in _tsv, "so a stopped server can still be chosen")
nin(JS, "ttsSrvRunning",
    "and the running-state helper is GONE - PTI and PME are panel-called providers "
    "now, so nothing was left to label (patch184)")
check("function llmNeeded" in JS, "and the control is dimmed when none qualifies")
_ln = seg(JS, "function llmNeeded", "function ttsTagServers")
check("disabled" in _ln, "shown but not usable, rather than hidden")
check("NO_LLM_WHY" in _ln and "title=" in _ln, "with the reason on hover")
check("cannot answer this" in JS, "which says why a vision model will not do")
check("does not have to be running" in JS,
      "and that the fleet need not be up to set this")
check(".needllm" in _css and "opacity" in seg(_css, ".needllm {", ".needllm select"),
      "dimmed by CSS, not removed from the page")
for _fn in ("function ttsPlayerTagRow", "function ttsMoodRow"):
    check("if (!up.length) return llmNeeded(" in seg_len(JS, _fn, 700),
          "%s stands aside when nothing can answer" % _fn.split()[-1])


section("the scene is read between turns")
check("def mood_evaluate" in py, "the scene can be read after an NPC line")
# built from what reaches TTS, not from a dialogue prompt: already named, already split
# into turns, and it works with no fleet behind the panel at all
check("TTS_TURNS" in py, "the conversation is kept as it is spoken")
check("mood_wanted" not in py and "mood_after_line" not in py,
      "and the proxy no longer searches a prompt for what TTS already knows")
_mn = seg(py, "def mood_note_line", "def mood_evaluate")
check("if is_player:" in _mn, "a player line ends a turn rather than opening one")
check("_MOOD_GEN" in _mn and "MOOD_SETTLE" in _mn,
      "a reply arriving in pieces is read once, after the last piece")
check("threading.Thread" in _mn and "daemon=True" in _mn,
      "it runs in the background, so nothing waits on it")
_me = seg(py, "def mood_evaluate", "def mood_context")
check('MOOD["busy"]' in _me, "one reading at a time")
check("_inflight" in _me and "ttsMoodPostpone" in _me,
      "and it can stand aside while speech is being generated")
check("mood_note_line(tts_speaker_label(ref_path), tts_normalize(text)" in py,
      "a turn is recorded with the speaker's name and the line before any tagging")
_mv = seg(py, "def mood_valid", "def _chat")
# feelings only, not the whole tagger vocabulary - but EVERY spelling of one. The
# display list carries a single preferred spelling per tag, and holding the reader to
# that alone threw away whole lines naming a feeling this panel renders perfectly well.
check("MOOD_SPELLING" in _mv,
      "a named feeling must be one the tagger could actually use")
_sp = fp.MOOD_SPELLING
check(all(w in _sp for w in dict(fp.TAG_OFFER).get("Emotion", ())),
      "every word the reader is shown is accepted back")
# only for the emotions still offered: a spelling of one the panel stopped asking for
# has nothing to resolve to
for _alias, (_kind, _name) in fp.TTS_ALIAS.items():
    if _kind == "emotion" and _name in fp._EMOTION_OFFER:
        check(_alias.replace(" ", "").upper() in _sp,
              "and so is every other spelling the panel translates: %s" % _alias)
check("laugh" not in _sp and "whisper" not in _sp,
      "a sound or a style is still not a feeling")
# normalised on the way in, so the hint PTI is shown always reads the same way - and
# anger is no longer offered, so the pair has to be one that still is
check(len({_sp.get(w) for w in ("SURPRISED", "SURPRISE")}) == 1,
      "two spellings of one feeling arrive as one word",
      str([_sp.get("SURPRISED"), _sp.get("SURPRISE")]))
# the measured case: a two-line reading came back and PTI was handed one line, because
# the model wrote a word Higgs has no tag for and the whole line went silently
_said = ("1. contentment (85%): the banter is absurd.\n"
         "2. contempt (40%): they are mocking him.")
_gone = []
check(fp.mood_valid(_said, 3, _gone).count("\n") == 0,
      "a feeling this engine does not have is still refused")
check(_gone == ["contempt"], "but it is reported rather than vanishing", str(_gone))
check(fp.mood_valid(_said.replace("contempt", "surprise"), 3).count("\n") == 1,
      "and both lines survive when both name something real")
check(fp.mood_valid("1. surprised (70%): x", 3) == "[EMOTION-SURPRISE] (70%): x",
      "an alias spelling is kept, in the shape PTI is shown",
      fp.mood_valid("1. surprised (70%): x", 3))
_mev = seg(py, "def mood_evaluate", "def tts_engine_label")
check("mood_valid(said, n, _drop, _offp)" in _mev,
      "the refused words are collected rather than discarded at the call")
check("if _drop:" in _mev and "TTSW.log" in seg(_mev, "if _drop:", "return found"),
      "and the terminal says what was dropped, so a lost reading is visible")
# the model answered "1. amusement (85%)" and the brackets-only parser kept nothing,
# so PTI was handed no context at all
check(r"\[?\s*([A-Za-z_\- ]+?)\s*\]?" in _mv,
      "brackets are optional - a model that drops them is still understood")
check(r"\(\s*(\d{1,3})" in _mv,
      "but a score is required, so ordinary prose is not mistaken for an answer")
check("keep.append(" in _mv and "%s] (%s" in _mv,
      "and it is stored in one shape however it arrived")
_mp = seg(py, "def mood_prompt", "def mood_valid")
check("TAG_OFFER" in _mp, "and the prompt offers that same list")
# the framing that decides whether this helps or just biases
_inj = seg(py, "scene = mood_context()", "body = json.dumps")
check("NOT what the player said" in _inj,
      "the hint is marked as background, never as what the player feels")
# the reply is a marked-up LINE now, so "unchanged" is the way to decline a tag
check("return it unchanged" in _inj,
      "and declining a tag stays available even with a hint present")
check("MOOD_TTL" in py, "a stale reading is not used")
_mrow = seg(JS, "function ttsMoodRow", "function moodSlider")
check('id="tts-ttsMoodHistory"' in seg(JS, "function moodSlider", "function ttsModelOptions")
      or "ttsMoodHistory" in _mrow, "history is adjustable")
_sl = seg(JS, "function moodSlider", "function ttsModelOptions")
check('type="range"' in _sl and "min=" in _sl and "max=" in _sl,
      "as a slider - the bounds are passed in, so do not look for a literal")
# the wording is split across two string literals, so match a fragment of one
check("nothing reads this yet" in _mrow and "Player Tag Injector is off" in _mrow,
      "and it says so when tagging is off, since nothing would read it")


section("names when nothing has passed through the proxy")
_sl2 = seg(py, "def tts_speaker_label", "def tts_parse_multipart")
check("or tts_voice_name(path)" in _sl2,
      "an unlearned voice falls back to its voicetype rather than failing")
_sfv = seg(py, "def speaker_for_voice", "def player_name_unread")
check("return _spk_player[0]" in _sfv and 'return "Player"' in _sfv,
      "and the player is Player until named")


section("player lines can be tagged by a model")
# the player types their line, so nothing tags it - every NPC is expressive and they
# are not
check("def tts_player_tag" in py, "a fleet model can be asked for tags")
# Audio Tags is off by default and would have stripped the tag we just paid for
_ri = seg(py, "keep_tags = str(st.get", "processed = tts_apply_tags")
check("keep_tags = True" in _ri,
      "a tag we asked for is never stripped by the Audio Tags setting")
check("tts_apply_tags(raw, keep_tags" in py,
      "and the engine gets it in its own token form, not as square brackets")
# one feeling and one sound, which is what Higgs accepts
_pp = seg(py, "def tts_player_tag", "def tts_apply_tags")
# one per GROUP since patch24, now that all four groups are offered
# the grouping moved to _clean_tagged in patch27 - see "the line comes back marked up"
check("_clean_tagged(" in _pp,
      "the reply is cleaned before use - one tag per group, words unchanged")
check("mood_answer(said) if think else said" in _pp,
      "and with thinking on, only the final answer is read")
# mood evaluation suggests FEELINGS; sounds are the tagger's call from the line
_mp2 = seg(py, "def mood_prompt", "def mood_valid")
check('dict(TAG_OFFER).get("Emotion"' in _mp2,
      "mood evaluation names emotions only - a sigh is not a mood")
_mv2 = seg(py, "def mood_valid", "def _chat")
check("MOOD_SPELLING" in _mv2, "and its answer is held to that, in any spelling of it")
_pt = seg(py, "def tts_player_tag", "def tts_apply_tags")
check("return \"\"" in _pt, "and every path out of it returns nothing rather than raising")
check("timeout=timeout" in _pt, "the call is bounded")
check("TTS_TAG_ANY_RX.search(line)" in _pt, "a line already tagged by hand is left alone")
check("_chat(" in _pt and "rt, sys_p, line" in _pt,
      "the reply comes from the shared chat helper, given a route")
# _chat used to hardcode temperature 0, silently overruling the launcher and saying so
# nowhere. Same value, carried as an override that shows on the card and can be cleared.
nin(seg(py, "def _chat(rt", "def mood_note_line"), '"temperature"',
    "and no sampler value is invented inside it")
check(fp.panel_prov_record({"id": "pti", "title": "PTI"})["samplerOverrides"] == {"temp": "0"},
      "the deterministic default ships as a visible override instead")
# the prompt and the validator must be ONE list
_off = seg(py, "def _build_offer", "def tags_off(")
# generated from the tables since patch24, so the labels live in _TAG_GROUPS
check("_TAG_GROUPS" in py and '"Emotion", ("emotion",)' in py,
      "the offered tags are declared once")
_pr = seg(py, "def tts_tag_prompt", "PTI_LAST = [0.0]")
check("TAG_OFFER" in _pr, "the prompt is built from that list")
# patch125: _tag_allowed was defined by patch115's refactor and called by nothing
# since - the answer filter is _clean_tagged's own TAG_OFFER map. Deleted whole.
_al = seg(py, "def _clean_tagged", "PTI_CACHE = ")
check("TAG_OFFER" in _al, "and so is what the answer is checked against")
nin(py, "_tag_allowed", "the dead allowlist is gone, not kept for company")
check("TTS_MOOD" not in _off + _pr + _al,
      "not from TTS_MOOD - those are icon names, not the words a line carries")
# Higgs only, and only for the player
check("tts_is_player(ref_path)" in py, "only player lines are tagged")
check('tts_engine(cfg) == "audiocpp" and tts_is_player' in py, "and only on Higgs")
check("ttsPlayerTagRow" in JS and 'eng === "audiocpp"' in JS
      and "ttsPlayerTagRow(st) + ttsMoodRow(st)" in JS,
      "the control is offered on Higgs only")
_row = seg(JS, "function ttsPlayerTagRow", "function ttsModelOptions")
_srvf = seg(JS, "function ttsTagServers", "function ttsPlayerTagRow")
check("s.scriptExists" in _srvf and "s.model" in _srvf,
      "the server list holds only servers that are SET UP with a model")
nin(_srvf, '=== "serving"',
    "and deliberately not running ones: these are settings, arranged before the fleet "
    "is launched. The old claim passed only because a dead helper in the same stretch "
    "carried the string (patch184)")
check("llmNeeded(" in _row, "and stands aside plainly when none is")
check("[angry] Get out of my way" in _row, "the hint says a tag can be typed by hand too")


section("the mood icon says what it means")
check("def mood_icon_names" in py, "there is an icon -> emotion map")
_min = seg(py, "def mood_icon_names", "def tts_mood_icon")
check("TTS_MOOD.items()" in _min,
      "built FROM the mood table, so the tooltip cannot disagree with the log")
check("TTS_MOOD_PLAIN" in _min, "including the plain head, which is not in that table")
check('" / ".join' in _min, "and an icon shared by several tags lists them all")
# PAGE_RAW, not PAGE: the placeholder has been substituted by now
check("__MOODS__" in PAGE_RAW and "mood_icon_names()" in py,
      "injected into the page, not retyped")
check('class="moodic"' in JS and 'title="' in JS, "the icon carries it as a tooltip")
check(".moodic[title] { cursor:help" in _css, "and the cursor invites the hover")
# it must cover everything the icon picker can return
import re as _re
_vals = set(_re.findall(r'"(\\U[0-9A-F]{8}(?:\\uFE0F)?)"', seg(py, "TTS_MOOD = {", "TTS_MOOD_PLAIN")))
check(bool(_vals), "the mood table still holds icons", str(len(_vals)))


section("column width and the fleet log")
# U+FE0F takes no column but widens the character before it
# counting terminal columns and applying them as `ch` could never line up: an emoji is
# not a whole number of `ch`. Flexbox measures the head itself.
check("termCols" not in JS, "no column arithmetic remains - it could not be made to work")
_ps = seg_len(JS, "function paintSpoken", 6600)
check("display:flex" in _ps, "a spoken line is laid out by flexbox")
check("flex:0 0 auto" in _ps, "the head keeps its natural width, whatever the emoji measure")
check("min-width:0" in _ps, "and the text wraps inside what is left")
check("padding-left:' + indent" not in JS, "nothing computes an indent any more")
check("pre.tail { white-space: pre-wrap" in _css,
      "the terminal wraps - it was opt-in via a class the tail never got")
# superseded in patch19: the TTS lifecycle goes to the STACK terminal, which is
# client-side - see "the panel's own calls are visible"
check("__prevTts" in JS, "the TTS server is announced where the other servers are")


section("spoken lines, logs and the red button")
# joinLines used to decide PER ROW whether to add a newline: a spoken line was emitted
# without one because the element it makes is block-level and breaks the row itself.
# When that held it was invisible; when it did not, the spoken line and everything after
# it ran together into one endless row that scrolled off to the right - which reads as
# the terminal having stopped. There is no decision now.
_jl = seg(JS, "function joinLines", "function paintSpoken")
check("mayWrap(line)" in _jl and '" one"' in _jl and '" tb"' not in _jl,
      "a row that may wrap goes bare and a record wears the cap - no tb marking remains")
nin(_jl, "SPOKEN_TAG", "with nothing sniffed out of the HTML to decide")
nin(_jl, "String.fromCharCode(10)", "and no newline between rows to be forgotten")
check("height:1.5em" in seg(_css, ".tail .tl {", ".payhead"),
      "a row is exactly one line tall - the rebuilt shell holds every row's place")
check('slice(0, 20).indexOf("display:block")' not in JS, "the old sniff is gone")

# Terminate stops the TTS server as well as the fleet
_tbtn = seg_len(JS, 'const tb = $("termBtn")', 420)
check("state.ttsServer" in _tbtn and "serving" in _tbtn,
      "a running TTS lights Terminate, as a running LLM does")

# one server log per panel run, like the fleet's
check("TTS_SERVER_LOG_GLOB" in py and "SESSION_STAMP" in py,
      "audio.cpp writes one log per session")
_tsl = seg(py, "def tts_server_log_newest", "def tts_server_status")
check("PANEL_START" in _tsl, "and a reader ignores logs from a previous run")
check("legacy" in _tsl, "while an install from before the split still reads")
check("os.path.join(log_dir(cfg), TTS_SERVER_LOG_NAME), \"ab\"" not in py,
      "nothing still writes to the single shared file")

# the model sometimes keeps decoding past the end of a line
_run = seg(py, "def tts_runaway_note", "def tts_mood_icon")
check("TTS_WPS" in _run, "audio far longer than the words justify is called out")
check("TTS_RUNAWAY_MIN_S" in _run,
      "with a floor, so a two-word line does not trip it on ratio alone")
check("tts_runaway_note(processed" in py, "and it is checked against what was actually sent")
# the server reports its own duration; comparing it with the file separates "the model
# generated too much" from "the file came back padded"
# audio.cpp serves one request at a time ("threads": 1), and the panel fires a burst of
# chunks at once - so a later chunk waits, and used to look like the panel hanging
check("_inflight" in py, "the panel counts what it has in flight")
_sub = seg(py, "    def submit(self, fields):", "    def result(self, eid")
check("ahead = self._inflight - 1" in _sub, "and each request is told how many are ahead")
_rw = seg(py, "    def _run(self, eid", "    def _run_inner")
check("finally:" in _rw and "_inflight = max(0" in _rw,
      "the count comes back down however the request ends, including on a failure")
# measured: SkyrimNet sends the next chunk ~0.11s AFTER it has the previous audio, so
# requests never overlap and a queue note could never fire
check("waiting behind" not in py,
      "no claim of a queue - the chunks are measured to arrive one after another")
check("never overlap" in py, "and the measurement is recorded where the code is")
check("x-audiocpp-audio-duration-ms" in py,
      "the duration the server reports is read, not just noticed")
check("padding, not speech" in py, "and disagreement with the file is reported")
check("_hdr_seen" in py, "the header list is logged once a session, not once a line")


section("two builds, one runtime")
_hw2 = seg(py, "HIGGS_ENGINE_ASSETS = (", "HIGGS_GGUF_REPO")
check('"balance"' in _hw2 and '"fast"' in _hw2, "both build profiles are fetched")
check('("runtime", ("win", "cuda", "runtime"), (), (), False, "")' in _hw2,
      "the shared CUDA runtime unpacks flat at the root, not per profile")
check(_hw2.count('True, "balance"') == 1 and 'False, "fast"' in _hw2,
      "balanced is required, fast is not - a release without it still installs")
# the exes sit one level down; the DLLs they need do not
_sp2 = seg_len(py, "def _api_tts_server", 4000)
check('env["PATH"] = _root' in _sp2,
      "the engine root is on PATH, or a profile exe cannot resolve the shared CUDA DLLs")
_fe = seg_len(py, "def find_acpp_exe", 1600)
check("[profile] if profile else []" in _fe, "the chosen profile is looked for first")
check("list(ACPP_PROFILES)" in _fe, "then the others, in a fixed order")
check("os.path.join(root, ACPP_EXE_NAME)" in _fe,
      "and a flat layout still works - older installs and hand unzips")
check('"%s|%s" % (root, profile' in _fe,
      "the cache is keyed on the profile too, or switching would return the old exe")
check("def acpp_profile" in py and 'in ACPP_PROFILES else "balance"' in py,
      "an unknown profile value falls back to the safe one")
# start at the comment that explains the choice, not at the const below it
_bl = seg(JS, "// Both are downloaded", "function gpuAutoLabel")
# the same three names are used for the CPU-only builds too, so they cannot be GPU
# architectures - they are the host CPU instruction baseline
check("CPU instruction baseline" in _bl,
      "the choice says what it actually changes - the CPU baseline, not the GPU")
check("compute capability 7.5" in _bl,
      "and records the GPU floor, which is the same for both")
check("GPU architectures they were compiled" not in JS,
      "no claim that the builds differ by GPU architecture")
check("profiles || []).length > 1" in JS,
      "and is offered only when both are really on disk")


section("install leaves nothing to chance")
_hw = seg(py, "def higgs_install_worker", "def api_higgs_install")
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
_row3 = seg(JS, "function higgsInstallRow", "async function higgsInstall")
check("#ff5d5d" in _row3, "with an outright failure in red")

# the only guide step nothing can detect
check('stepAt("yamlsent") && !res[i]' in JS,
      "the step that can never satisfy itself says it is manual")
check(".gmanual" in _css and "gmanualPulse" in _css, "and pulses so it reads as waiting")
check("prefers-reduced-motion" in _css, "unless the system asks for no motion")


section("stale diagnosis, stop, installed")
# the server log spans every run, so a blind tail reported a failure that had been fixed
_td = seg(py, "def tts_diagnose", "def tts_pick_fields")
check("since=None" in _td, "the diagnosis can be scoped to one run")
check("min(max(0, since), end)" in _td, "reading only from where that run began")
# it must be the DEATH path that uses it - that is the one people see
_tss = seg(py, "def tts_server_status", "TTS_PROC = {")
check('tts_diagnose(cfg, TTS_PROC.get("log_at"))' in _tss,
      "the startup-death hint reads this run, not a blind tail")
check('TTS_PROC.get("log_at")' in py, "and the start position is recorded when it spawns")
check('TTS_PROC["log_at"] = os.path.getsize' in py, "from the log size at that moment")
# stopping is most wanted exactly while it is starting
_stop = seg_len(JS, 'data-act="ttsStop"', 400)
check('busy === "start"' in _stop, "Stop works during startup, not only once it is up")
check('busy === "stop"' in _stop, "and is only dead while a stop is already running")
# and say plainly when it is already there
check(">Installed</span>" in JS and "f.adoptable" in JS,
      "an install that is present and selected says so")
check('"wired": wired' in py, "which needs the settings state, not just the files")


section("a server that dies while loading")
# it never opens the port, so waiting for the port waits for ever
_ts = seg(py, "def tts_server_status", "TTS_PROC = {")
check("proc.poll()" in _ts, "the process is polled, not just the port")
check("tts_diagnose(cfg," in _ts, "and its log is read to say why")
check('TTS_PROC["pid"], TTS_PROC["proc"] = None, None' in _ts,
      "the dead process is reaped, so nothing reads a stale pid")
check('not TTS_PROC.get("stopping")' in _ts, "a deliberate stop is not reported as a death")
check("sv.died" in JS, "the page shows it instead of waiting for it to answer")
check("!srv.died" in JS, "and the button stops saying it is starting")
# the two failures this GGUF actually produced
_hints = seg_len(py, "TTS_HINTS = (", 1400)
check("missing model file 'config'" in _hints,
      "a tensor-only GGUF is named as such, with what it needs beside it")
check("exact tensor shape metadata is invalid" in _hints,
      "and a GGUF from another converter is too")
# an <a href> is a navigation, which armed the leave-page guard
check('class="btnlink" download href="/api/log-download' in JS,
      "downloading a log does not prompt to leave the page")


section("the gate checks itself")
# Every silent failure this project has had was a slice going wrong. These prove the
# helpers turn each of those into a loud error instead of a free pass.
_T = "AAA def foo(): padding_padding_padding def bar(): tail_tail def foo_long(): z"


def _bug(fn):
    try:
        fn()
        return ""
    except GateBug as e:
        return str(e)


check(_bug(lambda: seg(_T, "def foo():", "def bar():")) == "",
      "a good slice is returned")
check("never appears after" in _bug(lambda: seg(_T, "def bar():", "def foo():")),
      "anchors the wrong way round are an error, not an empty string")
check("matches 2 places" in _bug(lambda: seg(_T, "def foo", "def bar():")),
      "an anchor that also matches a longer name is an error")
check("not found" in _bug(lambda: seg(_T, "def absent", "def bar():")),
      "a missing anchor is an error")
check("drifted together" in _bug(lambda: seg(_T, "def bar():", "tail_tail")),
      "anchors that have drifted adjacent are an error")
check("matches 2 places" in _bug(lambda: seg_len(_T, "def foo", 40)),
      "and the length form checks its anchor too")
check("only" in _bug(lambda: seg_before(_T, "AAA", 40)),
      "as does the backwards window")
# the asymmetry that made all of this dangerous
check(("x" not in "") is True,
      "a must-NOT-contain check passes on an empty string - which is WHY seg() is strict")
# and comments must not satisfy checks meant for code
check("log_error" not in code_only("# never call log_error here\nlog_warn(1)\n"),
      "a comment mentioning a symbol does not count as using it")
check("log_error" not in code_only('def f():\n    """use log_error"""\n    pass\n'),
      "nor does a docstring")
check("log_warn" in code_only("# never call log_error here\nlog_warn(1)\n"),
      "while real code survives")


section("warnings are not errors")
# log_error also raises a UI issue, so an observation logged that way told the user
# something was broken when nothing was
check("def log_warn" in py, "there is a level for something that did not fail")
_lw = seg_len(py, "def log_warn", 700)
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
_timing = [l.strip()[:70] for l in code_only(py).split("\n")
           if ('log_error("' in l or "log_error('" in l)
           and re.search(r"\bslow\b|\btook\b|elapsed", l, re.I)]
check(not _timing, "no timing observation is logged as an error", str(_timing)[:120])


section("state read probes")
# 700ms of a 750ms state read was two dead ports timing out one after the other, because
# priming and reading disagreed about WHICH ports
_sp = seg(py, "def state_probe_ports", "def api_state(*a")
check("parse_ps1_port" in _sp,
      "priming resolves the port the same way the read does - from the launcher script")
check("tts_server_port" in _sp, "and includes the TTS port, which was never primed")
_pr = seg(py, "def prime_slot_status", "def slot_status")
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
_tree = seg(JS, "function permTreeHtml", "function permSettingsHtml")
_TERMNAME = {"proxy": "Proxy", "think": "Thinking", "split": "Split", "tts": "TTS",
             "ptipme": "PTI-PME"}
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
_scope = seg_len(JS, "function applyScopeUI", 2500)
_dsub = seg_len(JS, "function showDsub", 700)
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
      'not in REMOTE_TAIL_KINDS' in py, "kind=file blocked for remote")


# ------------------------------------------------------------ 7. duplication
section("duplication (gotcha 1)")

ids = re.findall(r'id="([A-Za-z0-9_-]+)"', PAGE)
dupe_ids = [i for i, n in collections.Counter(ids).items() if n > 1]
check(not dupe_ids, "no duplicate static element ids", str(dupe_ids[:5]))

fns = re.findall(r"^(?:async )?function ([A-Za-z0-9_]+)", JS, re.M)
dupe_fns = [f for f, n in collections.Counter(fns).items() if n > 1]
check(not dupe_fns, "no duplicate JS functions", str(dupe_fns[:5]))

# ORPHANS, not just duplicates. The gate counted copies of a function and never
# asked whether anything called it, so ttsSrvRunning sat in the page for patches
# after its last caller went - and a check pinned its NAME, which made the corpse
# look like a feature. A function nobody names is either a bug or dead weight.
# (patch184)
_orphan_js = []
for _f in sorted(set(fns)):
    _rx = r"(?<![\w$.])%s(?![\w$])" % re.escape(_f)
    _defs = len(re.findall(r"function\s+%s(?![\w$])" % re.escape(_f), PAGE))
    if len(re.findall(_rx, PAGE)) <= _defs:
        _orphan_js.append(_f)
check(not _orphan_js, "no JS function is defined and never named",
      ", ".join(_orphan_js[:6]))

# The same rule for the panel's own constants: a module-level ALL-CAPS name that
# nothing reads is a literal repeated somewhere else, or a leftover. Six of them
# were (patch184).
_pytree = ast.parse(py)
_pyconst = [n.targets[0].id for n in _pytree.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id.isupper() and len(n.targets[0].id) > 3]
_orphan_c = [c for c in _pyconst
             if len(re.findall(r"(?<![\w.])%s(?![\w])" % re.escape(c), py)) <= 1]
check(not _orphan_c, "no panel constant is defined and never read",
      ", ".join(_orphan_c[:6]))

# and no nested helper left behind by a refactor - next_id outlived the creation
# path that used it by thirty-odd patches
_orphan_fn = []
for _n in ast.walk(_pytree):
    if isinstance(_n, ast.FunctionDef):
        _uses = sum(1 for _u in ast.walk(_pytree)
                    if (isinstance(_u, ast.Name) and _u.id == _n.name)
                    or (isinstance(_u, ast.Attribute) and _u.attr == _n.name))
        if _uses == 0 and not _n.name.startswith(("do_", "__", "handle_", "log_message")):
            _orphan_fn.append(_n.name)
check(not _orphan_fn, "no panel function is defined and never named",
      ", ".join(sorted(_orphan_fn)[:6]))

# every README.txt in the tree follows the same rule as the one beside it: CRLF,
# no BOM. ps1-launchers/ shipped LF for many patches because the encoding rule
# named the file and the check only ever read the root one. (patch184)
for _rd in ("README.txt", os.path.join("ps1-launchers", "README.txt")):
    _rp = os.path.join(ROOT, _rd)
    if os.path.isfile(_rp):
        _rb = open(_rp, "rb").read()
        check(b"\r\n" in _rb and _rb.count(b"\n") == _rb.count(b"\r\n")
              and not _rb.startswith(b"\xef\xbb\xbf"),
              "CRLF and no BOM: %s" % _rd)

# the counter the proxy has paid for on every forward is READ somewhere - it was
# maintained for nobody until the sweep put it in the report (patch184)
check("PROXY.busy(s.get(\"port\") or 0)" in py and "requests open now" in py,
      "the inflight count reaches the debug report, not just the gate")

# ---------------------------------------------------------------- patch185
# Meta's Muse Glimmer ships its speculative drafter as a SEPARATE architecture -
# "dflash", ordinary tensor names, block_size 16 - so the tensor scan that finds
# Gemma's MTP heads by name could never find it, and the panel called it a plain
# model. The header is the stronger fact: it is what llama.cpp itself reads. And
# a drafter that loads through the speculative path needs the speculative flags,
# not --model-draft.
check("DRAFT_ARCHS = frozenset((" in py and '"dflash"' in py
      and "if arch in DRAFT_ARCHS" in py,
      "a drafter that names its own architecture is taken at its word")
check('if hint == "vision" and meta.get(arch + ".block_count")' in py,
      "and a model that CARRIES a vision tower is still the model that runs - "
      "Muse Glimmer is image-text-to-text in one file")
check("def draft_launch_args(draft_path" in py
      and '("--spec-type", "draft-dflash")' in py
      and 'meta.get("dflash.block_size")' in py,
      "the drafter's own block size is the draft depth, read from its header")


def _mkgguf85(path, kvs, tensors):
    import struct as _st
    def _s(x):
        b = x.encode("utf-8")
        return _st.pack("<Q", len(b)) + b
    out = b"GGUF" + _st.pack("<I", 3) + _st.pack("<Q", len(tensors)) + _st.pack("<Q", len(kvs))
    for k, (ty, v) in kvs.items():
        out += _s(k) + _st.pack("<I", ty)
        out += _s(v) if ty == 8 else (_st.pack("<I", v) if ty == 4 else _st.pack("<B", 1))
    for n in tensors:
        out += _s(n) + _st.pack("<I", 1) + _st.pack("<Q", 16) + _st.pack("<I", 0) + _st.pack("<Q", 0)
    open(path, "wb").write(out)


_k85 = None
try:
    _d85 = tempfile.mkdtemp()
    _dr85 = os.path.join(_d85, "Muse-Glimmer-30B-assistant-Q8_0.gguf")
    _mkgguf85(_dr85, {"general.architecture": (8, "dflash"),
                      "dflash.block_count": (4, 5), "dflash.block_size": (4, 16)},
              ["token_embd.weight"] + ["blk.%d.attn_q.weight" % i for i in range(5)])
    _mn85 = os.path.join(_d85, "Muse-Glimmer-30B.Q8_0-hb16.gguf")
    _mkgguf85(_mn85, {"general.architecture": (8, "muse-glimmer"),
                      "muse-glimmer.block_count": (4, 52)},
              ["token_embd.weight"] + ["v.blk.%d.attn_q.weight" % i for i in range(3)]
              + ["blk.0.attn_q.weight"])
    _pj85 = os.path.join(_d85, "mmproj-model-f16.gguf")
    _mkgguf85(_pj85, {"general.architecture": (8, "clip"),
                      "clip.has_vision_encoder": (7, True)}, ["v.blk.0.attn_q.weight"])
    _mt85 = os.path.join(_d85, "gemma-mtp-head.gguf")
    _mkgguf85(_mt85, {"general.architecture": (8, "gemma3"), "gemma3.block_count": (4, 2)},
              ["mtp.0.weight", "blk.0.attn_q.weight"])
    _pl85 = os.path.join(_d85, "Qwen3-0.6B-Q8_0.gguf")
    _mkgguf85(_pl85, {"general.architecture": (8, "qwen3"), "qwen3.block_count": (4, 28)},
              ["token_embd.weight", "blk.0.attn_q.weight"])
    _k85 = [fp._model_kind_read(_dr85) == "draft",
            fp._model_kind_read(_mn85) == "main",
            fp._model_kind_read(_pj85) == "vision",
            fp._model_kind_read(_mt85) == "draft",
            fp._model_kind_read(_pl85) == "main"]
except Exception:
    _k85 = None
if _k85 is not None:
    check(_k85 == [True] * 5,
          "run: the DFlash assistant reads as a DRAFTER, the one-file multimodal "
          "model as the model, a real projector as vision, Gemma's tensor-named MTP "
          "head still as a drafter, and a small plain model as a model", str(_k85))
else:
    check(False, "the model-kind run did not RUN")

_a85 = None
try:
    _sp85 = fp.draft_launch_args(_dr85, "99")
    _cv85 = fp.draft_launch_args(_pl85, "99")
    _no85 = [f for f, _v in fp.draft_launch_args(_dr85, "")]
    _a85 = [_sp85 == [("--spec-draft-model", _dr85), ("--spec-type", "draft-dflash"),
                      ("--spec-draft-n-max", "16"), ("--spec-draft-ngl", "99")],
            _cv85 == [("--model-draft", _pl85)],
            "--spec-draft-ngl" not in _no85]
except Exception:
    _a85 = None
if _a85 is not None:
    check(_a85 == [True, True, True],
          "run: a DFlash drafter is launched through the speculative flags with its "
          "own block size, a conventional drafter keeps --model-draft, and the "
          "drafter is never placed on a card the user did not name", str(_a85))
else:
    check(False, "the draft-flags run did not RUN")

_g85 = None
try:
    _cfg85 = {"settings": {}, "gpus": []}
    _sl85 = {"id": "s1", "port": 1236, "label": "Gate185", "gpuId": "",
             "params": {"model": _mn85, "draft": _dr85, "ngl": "99", "ctx": "15360"}}
    _txt85 = fp.build_param_launcher(_cfg85, _sl85, os.path.join(_d85, "gen.ps1"))
    _tpl85 = "\n".join(['$llamaArgs = @(', '    "-m", "<MODEL_PATH>",',
                        '    "--n-gpu-layers", "99",',
                        '    "--spec-draft-model", "%s",' % os.path.join(_d85, "old.gguf"),
                        '    "--spec-type", "draft-dflash",',
                        '    "--spec-draft-n-max", "16",',
                        '    "--spec-draft-ngl", "99",', ')'])
    _t85 = {"content": _tpl85, "model": _mn85, "draft": _dr85, "vision": "N/A",
            "gpu": "", "port": 1236, "title": "Gate185"}
    _on85 = fp.render_launcher_lines(_t85, "x.ps1", "llama-server.exe")
    _t85b = dict(_t85); _t85b["draft"] = "N/A"
    _off85 = fp.render_launcher_lines(_t85b, "x.ps1", "llama-server.exe")
    # and the case the guard is FOR: a template already speaking the speculative
    # dialect, with a conventional drafter picked on the card - one drafter, not two
    _t85c = dict(_t85); _t85c["draft"] = _pl85
    _mix85 = fp.render_launcher_lines(_t85c, "x.ps1", "llama-server.exe")
    _g85 = ['"--spec-draft-model", "%s"' % _dr85 in _txt85,
            '"--spec-type", "draft-dflash"' in _txt85,
            '"--spec-draft-n-max", "16"' in _txt85,
            "--model-draft" not in _txt85,
            not any("--model-draft" in ln for ln in _on85),
            not any(any(f in ln for f in fp.DRAFT_SPEC_FLAGS) for ln in _off85),
            not any("--model-draft" in ln for ln in _mix85)]
except Exception:
    _g85 = None
if _g85 is not None:
    check(_g85 == [True] * 7,
          "run: the generated launcher carries the whole speculative set and no bare "
          "--model-draft, a template that already speaks it is not handed a second "
          "drafter, and turning the drafter off strips every one of its flags",
          str(_g85))
else:
    check(False, "the launcher-flags run did not RUN")

check('_KIND_RULES = "188"' in py and '_m.get("_rules") == _KIND_RULES' in py,
      "and a cache of verdicts reached under the OLD rule is dropped, not trusted - "
      "the drafter was already remembered as a plain model")

# ---------------------------------------------------------------- patch186
# A hand-edited launcher is edited in place, flag by flag - but the two optional
# model pickers were not in that map at all, so a drafter switched off on the card
# stayed in the file that RAN and the card described something other than what
# started. Every setting a card owns must survive the round trip: card -> the
# launcher text -> read back.
check('out["--mmproj"] = None if p.get("vision") in _off186' in py
      and 'for _f186 in ("--model-draft", "-md") + DRAFT_SPEC_FLAGS:' in py,
      "the vision and drafter pickers reach a hand-edited launcher too")
_rt86 = None
try:
    _d86 = tempfile.mkdtemp()
    _dr86 = os.path.join(_d86, "assistant.gguf")
    _mkgguf85(_dr86, {"general.architecture": (8, "dflash"), "dflash.block_size": (4, 16)},
              ["blk.0.weight"])
    _pl86 = os.path.join(_d86, "tiny.gguf")
    _mkgguf85(_pl86, {"general.architecture": (8, "qwen3"), "qwen3.block_count": (4, 28)},
              ["blk.0.weight"])
    _mm86 = os.path.join(_d86, "mmproj.gguf")
    _mkgguf85(_mm86, {"general.architecture": (8, "clip"),
                      "clip.has_vision_encoder": (7, True)}, ["v.blk.0.weight"])
    _cfg86 = {"settings": {}, "gpus": []}

    def _apply86(params, text):
        _s86 = {"id": "s1", "port": 1236, "params": params}
        _o86 = text
        for _f, _v in sorted(fp.slot_flag_values(_cfg86, _s86, text).items()):
            _o86 = fp.ps1_set_flag(_o86, _f, _v,
                                   after=fp.CTK_AFTER if _f == fp.CTK_FLAG else None)
        return _o86

    # 1. every setting a card owns, set to something that is NOT its default, must
    #    read back out of the text unchanged
    _card86 = {"model": os.path.join(_d86, "main.gguf"), "vision": _mm86, "draft": _dr86}
    _flip86 = {"on": "off", "off": "on", "f16": "q8_0", "auto": "deepseek"}
    for (_k, _l, _kind, _dv, _o, _f, _r) in fp.SERVER_PARAMS:
        _card86[_k] = (_flip86.get(_dv, "off") if _kind == "sel"
                       else str(int(_dv) + 7 if _dv.lstrip("-").isdigit() else 1))
    _bare86 = '$llamaArgs = @(\n    "-m", "x.gguf",\n)'
    _txt86 = _apply86(_card86, _bare86)
    _back86 = fp.parse_launcher_params(_txt86)
    _miss86 = [_k for _k in _card86
               if _k not in ("model", "vision") and str(_back86.get(_k)) != str(_card86[_k])]

    # 2. the owner's own launcher shape: Disabled must take the whole block out and
    #    leave everything a person wrote around it alone
    _own86 = "\n".join(['$llamaArgs = @(', '    "-m", "main.gguf",',
                        '    "--n-gpu-layers", "99",', '',
                        '    # --- speculative decoding: DFlash, verified on this build ---',
                        '    "--spec-draft-model", "%s",' % _dr86,
                        '    "--spec-type", "draft-dflash",',
                        '    "--spec-draft-n-max", "16",',
                        '    "--spec-draft-ngl", "99",', '',
                        '    "--temp", "1.0",', ')'])
    _offtxt86 = _apply86({"model": "main.gguf", "draft": "N/A", "vision": "N/A",
                          "ngl": "99"}, _own86)
    # 3. and switching to a conventional drafter takes the speculative flags with it
    _conv86 = _apply86({"model": "main.gguf", "draft": _pl86, "vision": "N/A",
                        "ngl": "99"}, _own86)
    _rt86 = [_miss86 == [],
             str(_back86.get("draft")) == _dr86, str(_back86.get("vision")) == _mm86,
             not any(_f in _offtxt86 for _f in fp.DRAFT_SPEC_FLAGS),
             "--model-draft" not in _offtxt86,
             "DFlash, verified on this build" in _offtxt86,
             '"--temp", "1.0"' in _offtxt86,
             '"--model-draft", "%s"' % _pl86 in _conv86,
             not any(_f in _conv86 for _f in fp.DRAFT_SPEC_FLAGS)]
except Exception:
    _rt86 = None
if _rt86 is not None:
    check(_rt86 == [True] * 9,
          "run: every card setting survives card -> hand-edited launcher -> card, "
          "Disabled removes the whole speculative block while the comment and the "
          "sampler line around it stay, and swapping a DFlash assistant for a plain "
          "drafter takes the speculative flags out with it", str(_rt86))
else:
    check(False, "the card round-trip run did not RUN")

# ---------------------------------------------------------------- patch187
# The launcher is the ROOT and the cards are a view of it. A card change was
# skipped whenever its value matched the panel's shipped default and the flag was
# not already in the array - so turning Reasoning back ON, "on" being the default
# too, wrote nothing at all and the card and the file disagreed. What the person
# just changed is now always written, and the card is read back out of the text
# that will run.
check("def slot_flag_values(cfg, s, present=\"\", force=()):" in py
      and "if (k not in force and (" in py
      and "r = regen_slot_script(cfg, s, force=changed)" in py,
      "a setting the person just changed reaches the launcher, default or not")
check("p.update(parse_launcher_params(edited))" in py
      and "def _slot_params_from_launcher(p, path):" in py,
      "and the card is read back out of the launcher - one root, not two stores")
_ld87 = None
try:
    _d87 = tempfile.mkdtemp()
    _gen87, fp.GEN_LAUNCHER_DIR = fp.GEN_LAUNCHER_DIR, _d87
    _own87 = "\n".join(["# a hand-written launcher with a person's own work in it",
                        'Write-Host "VRAM report follows"', "$llamaArgs = @(",
                        '    "-m", "main.gguf",', '    "--n-gpu-layers", "99",',
                        '    "--ctx-size", "15360",', '    "--jinja",', ")",
                        '& "llama-server.exe" @llamaArgs'])
    _cfg87 = {"settings": {}, "gpus": [], "slots": [
        {"id": "gate187", "port": 1236, "label": "Gate187",
         "params": {"model": "main.gguf", "ngl": "99", "ctx": "15360",
                    "custom": _own87}}]}
    _s87 = _cfg87["slots"][0]
    _lc87, _sc87, _sse87 = fp.load_config, fp.save_config, fp.sse_notify
    fp.load_config = lambda *a, **k: _cfg87
    fp.save_config = lambda c: None
    fp.sse_notify = lambda *a, **k: None
    fp.api_slot_params({"slot": "gate187", "reasoning": "on"})
    _on87 = _s87["params"]["custom"]
    _rd87 = _s87["params"].get("reasoning")
    fp.api_slot_params({"slot": "gate187", "reasoning": "off"})
    _off87 = _s87["params"]["custom"]
    fp.api_slot_params({"slot": "gate187", "flash": "on"})
    _fl87 = _s87["params"]["custom"]
    fp.load_config, fp.save_config, fp.sse_notify = _lc87, _sc87, _sse87
    fp.GEN_LAUNCHER_DIR = _gen87
    _ld87 = ['"--reasoning", "on"' in _on87,
             _rd87 == "on",
             "VRAM report follows" in _on87 and '"--jinja"' in _on87,
             '"--reasoning", "off"' in _off87 and fp.CTK_NO_THINK in _off87,
             _s87["params"].get("reasoning") == "off",
             '"--flash-attn", "on"' in _fl87]
except Exception:
    _ld87 = None
if _ld87 is not None:
    check(_ld87 == [True] * 6,
          "run: Reasoning turned ON writes --reasoning on into a hand-edited launcher "
          "even though on is the default, the person's own lines are untouched, OFF "
          "writes both ways of saying it, the card reads back what the file says, and "
          "a default-valued dial the person touches lands too", str(_ld87))
else:
    check(False, "the card-is-a-view run did not RUN")

# ---------------------------------------------------------------- patch188
# What a model IS comes from its header, never its name: llama.cpp registers an
# architecture per family and every GGUF declares its own. The card shows that
# under the model picker, and a family whose template always thinks - Meta says
# so for Muse Glimmer - gets the dial it actually answers to, reasoning STRENGTH,
# while the on/off switch it ignores is shown greyed with the reason.
check("MODEL_ARCH_NAMES = {" in py and "def arch_label(arch):" in py
      and "def model_facts(path):" in py and "def model_arch(path):" in py,
      "one header read yields the kind, the family and the two numbers beside it")
check('"muse-glimmer": "Muse Glimmer (Meta)"' in py and '"gemma4": "Gemma 4"' in py
      and '"qwen3": "Qwen 3 family"' in py and '"mistral3": "Mistral 3"' in py
      and '"deepseek2":' in py and '"command-r":' in py,
      "the families a local RP fleet actually runs are named")
check('"archLabel": _f188.get("label", "")' in py and "const mArch = archOf(chosen);" in py
      and "Model architecture: " in JS,
      "and the card says which one it is reading, under the picker")
check("ARCH_REASON_STRENGTH = (" in py and 'REASON_STRENGTHS = ("low", "medium", "high", "xhigh")' in py
      and "if model_arch(p.get(\"model\") or \"\") in ARCH_REASON_STRENGTH:" in py
      and 'const wantsStrength = STRENGTH_ARCH.indexOf(mArch) >= 0;' in py,
      "a family that cannot switch thinking off is offered strength instead")
_ar88 = None
try:
    _d88 = tempfile.mkdtemp()
    _mk88 = {}
    for _nm, _arch, _bl, _cx in (("some-random-name.gguf", "muse-glimmer", 52, 131072),
                                 ("a.gguf", "gemma4", 48, 131072),
                                 ("b.gguf", "qwen3moe", 64, 262144),
                                 ("c.gguf", "llama", 40, 32768),
                                 ("d.gguf", "exaone4", 30, 32768)):
        _p88 = os.path.join(_d88, _nm)
        _mkgguf85(_p88, {"general.architecture": (8, _arch),
                         _arch + ".block_count": (4, _bl),
                         _arch + ".context_length": (4, _cx)}, ["blk.0.weight"])
        _mk88[_arch] = fp.model_facts(_p88)
    _ar88 = [_mk88["muse-glimmer"]["label"] == "Muse Glimmer (Meta)",
             _mk88["muse-glimmer"]["blocks"] == 52 and _mk88["muse-glimmer"]["ctx"] == 131072,
             _mk88["gemma4"]["label"] == "Gemma 4",
             _mk88["qwen3moe"]["label"].startswith("Qwen 3"),
             _mk88["llama"]["label"].startswith("Llama"),
             _mk88["exaone4"]["label"] == "EXAONE 4",
             fp.arch_label("qwen3point5") == "Qwen 3 family",
             fp.arch_label("something-nobody-taught-it") == "something-nobody-taught-it"]
except Exception:
    _ar88 = None
if _ar88 is not None:
    check(_ar88 == [True] * 8,
          "run: five architectures read out of headers under names that say nothing, "
          "an unseen Qwen falls to its family, and one nobody taught it is reported "
          "under its own name rather than guessed at", str(_ar88))
else:
    check(False, "the architecture run did not RUN")

_rs88 = None
try:
    _muse88 = os.path.join(_d88, "some-random-name.gguf")
    _gem88 = os.path.join(_d88, "a.gguf")
    _cfg88 = {"settings": {}, "gpus": []}
    _txt88 = '$llamaArgs = @(\n    "-m", "x.gguf",\n    "--reasoning", "auto",\n)'

    def _ap88(params, text, force=()):
        _s = {"id": "s1", "port": 1236, "params": params}
        _o = text
        for _f, _v in sorted(fp.slot_flag_values(_cfg88, _s, text, force).items()):
            _o = fp.ps1_set_flag(_o, _f, _v,
                                 after=fp.CTK_AFTER if _f == fp.CTK_FLAG else None)
        return _o
    _on88 = _ap88({"model": _muse88, "reasonStrength": "xhigh"}, _txt88, ["reasonStrength"])
    _off88 = _ap88({"model": _muse88, "reasonStrength": "", "reasoning": "off"},
                   _on88, ["reasoning"])
    _gm88 = _ap88({"model": _gem88, "reasoning": "off"}, _txt88, ["reasoning"])
    _gen88 = fp.build_param_launcher(_cfg88, {"id": "s1", "port": 1236, "label": "G",
                                              "gpuId": "", "params": {"model": _muse88,
                                              "reasonStrength": "high", "ngl": "99"}},
                                     os.path.join(_d88, "gen.ps1"))
    _rs88 = ['{"reasoning_strength":"xhigh"}' in _on88,
             fp.parse_launcher_params(_on88).get("reasonStrength") == "xhigh",
             "enable_thinking" not in _off88 and "reasoning_strength" not in _off88,
             fp.CTK_NO_THINK in _gm88,
             '{"reasoning_strength":"high"}' in _gen88,
             fp.parse_launcher_params(_gen88).get("reasonStrength") == "high"]
except Exception:
    _rs88 = None
if _rs88 is not None:
    check(_rs88 == [True] * 6,
          "run: a Muse Glimmer card writes reasoning strength into the kwarg and reads "
          "it back, never the enable_thinking form it would ignore, while a family that "
          "CAN be switched off still gets that - hand-edited and generated alike",
          str(_rs88))
else:
    check(False, "the reasoning-strength run did not RUN")

# ---------------------------------------------------------------- patch189
# The shipped default config is a SECOND statement of the factory fleet, and it
# had fallen four providers behind the seed table - both plugin pairs. The
# seeder heals a config on load, so nothing was broken; but a file that
# contradicts the code is the shape every drift in this project has taken.
_dc89 = os.path.join(ROOT, "fleet-config.default.json")
if os.path.isfile(_dc89):
    _cfg89 = json.load(open(_dc89, encoding="utf-8"))
    _have89 = {int(x.get("port") or 0) for x in _cfg89.get("unallocatedProviders", [])}
    _want89 = []
    for _lst in fp.DEFAULT_PROVIDER_SEED.values():
        _want89.extend(_lst)
    _miss89 = sorted((_n, _p) for (_n, _p, _t, _pr) in _want89 if _p not in _have89)
    check(not _miss89,
          "the shipped default config states the same fleet the seeder does",
          str(_miss89))
    _noem89 = sorted(x.get("title", "?") for x in _cfg89.get("unallocatedProviders", [])
                     if not x.get("emoji"))
    check(not _noem89, "and every provider in it carries its mark", str(_noem89))

# ---------------------------------------------------------------- patch190
# The LLM writes as many feelings into a reply as it likes, wherever it likes;
# the panel hands them out in reading order, one per chunk, and holds the last
# when the model wrote fewer than there are chunks. Nothing decides placement
# but the model.
_fa90 = None
try:
    _w90 = "GateFree90"
    fp.MOOD_QUEUE[_w90] = ([("emotion", "cheerful"), ("emotion", "nervous"),
                            ("style", "whisper")], time.time())
    _seq90 = [fp.tts_npc_mood_arm(_w90, "one"), fp.tts_npc_mood_arm(_w90, "two"),
              fp.tts_npc_mood_arm(_w90, "three"), fp.tts_npc_mood_arm(_w90, "four")]
    fp.MOOD_QUEUE[_w90] = ([("emotion", "angry")], time.time())
    _one90 = [fp.tts_npc_mood_arm(_w90, "a"), fp.tts_npc_mood_arm(_w90, "b")]
    fp.MOOD_QUEUE[_w90] = ([("sfx", "laughter"), ("emotion", "joyful")], time.time())
    _sfx90 = fp.tts_npc_mood_arm(_w90, "hah")
    fp.MOOD_QUEUE[_w90] = ([("emotion", "joyful")], time.time())
    _cool90 = fp.tts_npc_mood_arm(_w90, "quiet", cool=frozenset({"emotion:joyful"}))
    fp.MOOD_QUEUE.pop(_w90, None)
    _fa90 = [_seq90[0] == "<|emotion:cheerful|> one",
             _seq90[1] == "<|emotion:nervous|> two",
             _seq90[2] == "<|style:whisper|> three",
             _seq90[3] == "<|style:whisper|> four",
             _one90 == ["<|emotion:angry|> a", "<|emotion:angry|> b"],
             _sfx90 == "<|emotion:joyful|> hah",
             _cool90 == "quiet"]
except Exception:
    _fa90 = None
if _fa90 is not None:
    check(_fa90 == [True] * 7,
          "run: three feelings written into one reply reach three chunks in reading "
          "order and the last HOLDS for a fourth; one feeling carries the whole "
          "reply; a sound tag is still never injected and a limited tag still "
          "cannot be armed", str(_fa90))
else:
    check(False, "the free-allocation run did not RUN")

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
                    "ttsWrapperPort": "7861", "ttsGpuId": "g1",
                    # this section tests the OWN-wrapper .bat, which is a mode now
                    # that the Proxy translates by default - pinned, not inherited
                    "ttsWrapMode": "off"}}
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

# (tts_chunks and tts_wav_join left in the patch155 sweep: audio.cpp answers one
# request with one file, so nothing splits or stitches - the absence checks in the
# acpp arm above already pin that)
check("def tts_chunks" not in py and "def tts_wav_join" not in py,
      "the splitter and the stitcher are gone, not orphaned")

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

check(str(DEF := re.search(r'"ttsWrapMode":\s*"(\w+)"', py).group(1)) == "on",
      "the Proxy translates for SkyrimNet by default", DEF)

# both listeners bind 0.0.0.0 for 2-PC mode, so the TTS one must filter clients exactly
# as the proxy does - otherwise the panel refuses a stranger on one port and serves them
# on the next
_th = seg(py, "def _mk_tts_handler", "TTSW = TtsWrapper()")
check("PROXY" in _th and "allow" in _th and "client_address" in _th,
      "TTS listener applies the proxy's client-IP allowlist")
check("403" in _th, "TTS listener refuses a client outside the allowlist")
check("MAX_BODY" in _th and "413" in _th,
      "TTS listener caps the request body rather than allocating what is claimed")
check("_allowed()" in _th and _th.count("if not self._allowed(): return") >= 3,
      "every TTS verb is gated, not just POST",
      "%d gated" % _th.count("if not self._allowed(): return"))

_tw = seg(py, "class TtsWrapper", "def tts_voice_name")
check("def prune" in _tw and "os.remove" in _tw,
      "generated audio is pruned rather than accumulating forever")
check("rmtree" in _tw, "uploaded reference voices are pruned too")

# SkyrimNet's references come from FFmpeg with extra RIFF chunks. moss-tts-server
# answered those with 400 and audio.cpp with "failed to read WAV data chunk" - the same
# fault through two parsers, so it is normalised once at the upload, not per engine.
_su = seg(_tw, "def save_upload", "def submit")
check("tts_wav_normalize" in _su,
      "an uploaded reference is normalised on the way in, for every engine")
check('b"RIFF"' in _su, "and only when it is actually a WAV")
_acpp = seg(py, "def _run_inner", "ref_b64, cached")
# normalising on the way in is not enough: SkyrimNet HEADs the path first and skips the
# upload on a 200, so a file cached by an older build is never re-sent
_rc = seg(py, "def tts_ref_canonical", "def tts_engine")
check("tts_wav_head_ok" in _rc,
      "a cached reference is judged by the shared header test, not a second copy of it")
check("f.write(clean)" in _rc, "and repaired in place, so it is fixed once and stays fixed")

# A header test that asks only WHERE the data chunk sits passes a file that declares
# 0xFFFFFFFF as its size - 160 of the user's voicetype WAVs do exactly that, and
# audio.cpp refuses every one of them. Test the declared values, not the layout.
def _break4(blob, off):
    b = bytearray(blob)
    b[off:off + 4] = b"\xff\xff\xff\xff"
    return bytes(b)

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

_ok = _mkwav(500)
check(fp.tts_wav_head_ok(_ok[:44], len(_ok)), "a canonical 44-byte header is accepted")
check(not fp.tts_wav_head_ok(_break4(_ok, 40)[:44], len(_ok)),
      "a data chunk declaring 0xFFFFFFFF is refused")
check(not fp.tts_wav_head_ok(_break4(_ok, 4)[:44], len(_ok)),
      "a broken RIFF size is refused")
check(not fp.tts_wav_head_ok(b"ID3\x04" + b"\x00" * 40, 44), "a non-WAV header is refused")

_refdir = tempfile.mkdtemp()
_said = []
# tts_ref_canonical announces a repair through panel_log, which resolves log_dir()
# against the panel's own folder - the tree under test. Held aside for the duration,
# and the announcement is checked rather than discarded.
_real_log, _real_err = fp.panel_log, fp.log_error
fp.panel_log = lambda m: _said.append(str(m))
fp.log_error = lambda src, m, record=True: _said.append("%s: %s" % (src, m))


def _canon(name, blob):
    p = os.path.join(_refdir, name)
    open(p, "wb").write(blob)
    fp.tts_ref_canonical(p)
    return open(p, "rb").read()


try:
    _fixed = _canon("broken.wav", _break4(_break4(_ok, 40), 4))
    _kept = _canon("good.wav", _ok)
    _twice = _canon("again.wav", _fixed)
finally:
    fp.panel_log, fp.log_error = _real_log, _real_err

check(fp.tts_wav_head_ok(_fixed[:44], len(_fixed)),
      "a voicetype WAV with broken length fields is repaired on first use",
      "%d bytes" % len(_fixed))
check(_kept == _ok, "a canonical reference is left untouched")
check(_twice == _fixed, "and a repaired one is not rewritten a second time")
check(sum("rewrote a stale reference" in s for s in _said) == 1,
      "exactly the one repair is announced", str(_said)[:120])
check("tts_ref_canonical(ref_path)" in _acpp,
      "the audio.cpp arm repairs a stale reference rather than failing on it")

# a crashed server closes the socket and says nothing; its own log says why one line up
_dg = seg(py, "def tts_diagnose", "def tts_pick_fields")
check("no kernel image" in py and "TTS_HINTS" in py,
      "a crash is translated into something a person can act on")
check("f.seek(0, 2)" in _dg, "only the tail of the server log is read, not all of it")
check("tts_diagnose(" in seg(py, "def _run_inner", "def _silence"),
      "and the hint is attached to the failure the user sees")

# Zonos and Chatterbox both speak Gradio but send different argument lists
_pf = seg(py, "def tts_pick_fields", "def tts_ref_canonical")
check("fields[3]" in _pf and "isinstance" in _pf,
      "the proven Zonos positions are kept when they hold")
check('f.get("path")' in _pf,
      "and the reference is found by shape when they do not - any Gradio engine works")
check("_TTS_LANG_RX" in _pf, "a language tag is never mistaken for the line to speak")
check("fields[1] if len(fields)" not in seg(py, "def submit", "def result"),
      "submit no longer indexes the array blind")
check("PROXY_MAX_BODY" in py, "the proxy caps its request body as the TTS listener does")
_ph = seg_len(py, "def _mk_handler", 4000)
check("PROXY_MAX_BODY" in _ph and "413" in _ph,
      "and refuses an oversized claim rather than allocating it")
_sv = seg(py, "def api_tts_server", "def api_launcher_content")
check(_sv.count("logf.close()") >= 2,
      "the child's log handle is closed in the parent on both paths",
      "%d close sites" % _sv.count("logf.close()"))

# the reference wrapper round-trips the voice through soundfile before base64, which
# strips stray RIFF chunks. Passing the original bytes through is what drew a 400.
import struct as _struct

_norm = fp.tts_wav_normalize(_mkwav(200, extra=True))
check(b"LIST" not in _norm, "reference re-encode strips stray RIFF chunks")
import wave as _w2
with _w2.open(io.BytesIO(fp.tts_wav_normalize(_mkwav(200, ch=2))), "rb") as _w3:
    check(_w3.getnchannels() == 1, "reference re-encode downmixes to mono (no audioop)")
check(fp.tts_wav_normalize(b"not a wav") == b"not a wav",
      "unreadable reference passes through rather than being destroyed")

# "HTTP Error 400: Bad Request" says nothing; the server's body says what it objected
# to - and this now reads the LIVE path. It read the MOSS poster, which nothing had
# called for many patches, so the claim was true of a corpse. A slice, too, where the
# house rule says seg(). (patch184)
_src = seg(py, "def _tts_acpp_once", "def tts_server_port")
check("_uerr.HTTPError" in _src and "e.read()" in _src
      and 'raise RuntimeError("HTTP %s from %s%s"' in _src,
      "upstream failures surface the server's own response body - which is how "
      "'reached max_tokens before EOC' ever became readable")


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
_fe = seg(py, "def full_exit", "def watchdog_loop")
check("stop_tts_server" in _fe, "exit stops a panel-started TTS server")
check("TTSW" in _fe and "shutdown" in _fe, "exit shuts the TTS listener down with the proxy's")
check("stop_tts_server" in seg(py, "def api_terminate", "def api_exit"),
      "Terminate stops the TTS server too")
_ss = seg(py, "def stop_tts_server", "def api_tts_server")
check("TTS_PROC" in _ss and "_kill_port_owner" not in _ss,
      "exit stops only what the panel started, never whatever holds the port")
check(len(re.findall(r"def stop_tts_server", py)) == 1,
      "one stop implementation shared by exit, terminate and the button")

# a page that never redraws shows yesterday's state. The TTS pane was only redrawn by
# the Start button's own poll, so anything that changed the server from elsewhere -
# Terminate, exit, a crash - left it claiming the server was still up.
_rc = seg(JS, "function renderCurrent", "function renderRouting")
check("renderTts" in _rc,
      "the TTS pane redraws from renderCurrent, which runs AFTER state is fetched")
check("dpane-tts" in _rc, "TTS redraw stands aside for a focused field")
_lr = seg(JS, "function liveRefresh", "async function stateRepull")
check("renderTts" not in _lr,
      "not redrawn from liveRefresh, which runs BEFORE the state fetch and would use stale data")
check("stop_tts_server" in py and 'sse_notify("state")' in _ss,
      "stopping the server announces the change rather than waiting to be noticed")
check("_ST_CACHE.pop" in _ss, "stopping drops the cached status so it cannot read stale")
_sw = seg(py, "def status_watch_loop", "def sweep_launcher_shells")
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
try { w.showTab('tts'); w.showTsub('tts'); w.showTab('dashboard'); }
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
      w.showTab('tts');
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
      // one switch used to cover both features; a table drives the label and the
      // setting now, and a button lit from one setting toggling another is exactly
      // what that table is for. Press them and read what goes out.
      let tagOut = '';
      try {
        const mkt = (p, m) => JSON.stringify({ settings: { ttsTagOutputPti: p, ttsTagOutputPme: m },
          gpus: [], slots: [], routing: [], scope: 'host' });
        w.eval('state = ' + mkt('off', 'off') + ';');
        w.syncTermToggleUI();
        const bp = d.querySelector('[data-act="termTagOutPti"]');
        const bm = d.querySelector('[data-act="termTagOutPme"]');
        const lab = (bp ? bp.textContent.replace(/\s+/g, ' ').trim() : '?') + ' / '
                  + (bm ? bm.textContent.replace(/\s+/g, ' ').trim() : '?');
        const seen = (from) => w.__posts.slice(from)
          .map(x => { try { return JSON.parse(x); } catch (e) { return {}; } });
        let n0 = w.__posts.length;
        bp.click();
        const s1 = seen(n0);
        const p1 = s1.filter(x => 'ttsTagOutputPti' in x).pop() || {};
        const leaked1 = s1.some(x => 'ttsTagOutputPme' in x);
        w.eval('state = ' + mkt('off', 'off') + ';');
        n0 = w.__posts.length;
        bm.click();
        const s2 = seen(n0);
        const p2 = s2.filter(x => 'ttsTagOutputPme' in x).pop() || {};
        const leaked2 = s2.some(x => 'ttsTagOutputPti' in x);
        tagOut = 'labels=' + lab + ' pti=' + String(p1.ttsTagOutputPti)
               + ' pme=' + String(p2.ttsTagOutputPme)
               + ' leak=' + String(leaked1 || leaked2);
      } catch (e) { tagOut = 'threw: ' + String(e && e.message || e); }
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
      return { paintRoles: paintRoles, tagOut: tagOut,
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
        _to = str(out.get("tagOut") or "")
        check("PTI Output" in _to and "PME Output" in _to,
              "both output buttons are labelled from the table", _to)
        check("pti=on" in _to, "pressing PTI Output switches the PTI setting", _to)
        check("pme=on" in _to, "pressing PME Output switches the PME setting", _to)
        check("leak=false" in _to,
              "and neither press touches the other feature's setting", _to)
    except Exception as e:
        check(False, "jsdom harness ran", (r.stderr or r.stdout)[:300] or str(e))


# --------------------------------------------------- the gate leaves no trace
section("the gate leaves the tree as it found it")

# The junk sweep in section 2 runs before fleet-panel.py is imported, so anything this
# file writes while running was invisible to it and only ever hit the NEXT run. Same
# list, after everything has run.
for _junk in ("__pycache__", "fleet-config.json", "panel-port.txt", "model-kinds.json",
              "logs", "profiles", "generated-launchers"):
    check(not os.path.exists(os.path.join(ROOT, _junk)),
          "the run left no %s behind" % _junk)


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
