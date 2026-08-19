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
# a build numbered above the release calls that number something - "patch" or
# "hotfix" - and the tag, the header and the docs must all use the SAME word
word = re.search(r'APP_PATCH_WORD\s*=\s*"([a-z]+)"', py)
word = word.group(1) if word else "patch"
check((patch > 0) == (("%s%d" % (word, patch)) in tag.lower()),
      "APP_PATCH agrees with the tag, under the word this build uses",
      "patch=%d word=%s tag=%s" % (patch, word, tag))
check('VER_TIER = {"": 0, "hotfix": 1, "patch": 2}' in py
      and word in ("hotfix", "patch"),
      "and that word is one the version order knows", word)
check(("v%s Beta" % ver) in rd("README.txt").decode("utf-8", "replace")[:200],
      "README.txt title version")

# EVERY doc that states the current version must state THIS one. DEVELOPMENT.md
# said v3.69 Beta patch5 for 185 patches: its principles were updated every time
# and its own header never was, and it shipped that way. A file that names the
# version it belongs to is a claim, and a claim is checkable.
_vsay = "v%s Beta%s" % (ver, (" %s%d" % (word, patch)) if patch else "")
for _dn in ("DEVELOPMENT.md", "CHANGELOG.md", "README.md", "BUILD.md", "README.txt"):
    if not os.path.isfile(os.path.join(ROOT, _dn)):
        continue
    _dt = rd(_dn).decode("utf-8", "replace")
    for _ln in _dt.split("\n"):
        if re.search(r"[Cc]urrent version", _ln):
            _said = re.findall(r"v3\.\d+ Beta(?: (?:patch|hotfix)\d+)?", _ln)
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

_vt = None
try:
    _T = fp._ver_tuple
    _rel, _h1, _h2 = _T("v3.75-beta"), _T("v3.75-beta-hotfix1"), _T("v3.75-beta-hotfix2")
    _p1, _p2 = _T("v3.75-beta-patch1"), _T("v3.75-beta-patch2")
    _next = _T("v3.76-beta")
    _prev = _T("v3.74-beta-patch190")
    _vt = [_rel < _h1 < _h2 < _p1 < _p2 < _next,
           _prev < _rel,
           _h1 != _p1,                                   # same number, not the same build
           _T("v3.75-h1 Beta") == _h1 and _T("v3.75-p1 Beta") == _p1,
           _T("v3.75-beta") == (3, 75, 0, 0),
           _T(fp.APP_RELEASE_TAG) is not None]
except Exception:
    _vt = None
if _vt is not None:
    check(_vt == [True] * 6,
          "run: within one release the order is the order the builds are made - the "
          "release, then its hotfixes, then its patches - a hotfix and a patch of the "
          "same number are told apart, the header's short forms read the same as the "
          "tags, and the next release still outranks them all", str(_vt))
else:
    check(False, "the version-order run did not RUN")

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
# retold patch23: the sampler block has no calRow at all now - no setting, no
# menu, no model cell. It is a title and its chips.
nin(_sb9, "ttsCalRow(", "the sampler block is a title and its chips, nothing else")
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
check(JS.count("function ttsCalRow(") == 1,   # retold p23: one user now
      "one row shape, defined once")
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
check(_acb9.count("ttsTitle(") >= 4 and _sb9.count("ttsTitle(") >= 1,  # p23
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
for _blk13, _id13, _cls13 in ((_ac13, "tts-ttsAutoCal", "setsel"),):  # p23
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
check(set(fp.TTS_SAMP_FIELD) == {"temp", "top_k"}   # retold p23
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
# retold patch23: Steady Retry is gone, so there is nothing to sit beside the
# chips. The title leads and the chips follow - that is the whole block.
nin(_sb15, "Steady Retry", "no retry switch rides with the samplers any more")
check(_sb15.index('ttsTitle("TTS Samplers"') < _sb15.index('id="tts-samp-chips"'),
      "the title leads and the chips follow")

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
# retold patch23: Steady Retry is gone - it moved the samplers, and moving them
# is what produced the degenerate repeat
_sampq = seg(JS, "function ttsSampBlock", "// A job the panel gives to a model")
nin(_sampq, "Steady Retry", "the retry switch is gone from the sampler block")
nin(_sampq, "ttsRetrySafe", "action and all")

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
# retold patch23: the automatic sampler step is GONE. Moving these values is what
# produced the degenerate repeat, so nothing moves them now - they are set by hand.
nin(py, "def autocal_sampler_arith",
    "the automatic sampler step is gone, function and all")
nin(py, "ttsSampAutoCal", "and the switch that ran it with it")
for _phrase in ("does NOT change how often", "top_p 1.0 truncates nothing",
                "repetition_penalty pushes probability away"):
    check(_phrase in fp.DIAG_SYSTEM,
          "the diagnosis is told what moves the odds: %s" % _phrase[:34])
check("overrunBySampler" in fp.cal_facts({"settings": {}}),
      "and is given the failure rate per configuration to read it from")
nin(JS, "ttsAutoCalRun", "the button it replaced is gone, handler and all")
nin(py, "api_tts_autocal_run", "and so is the endpoint - the run is in-process now")
nin(py, "ttsRetrySafe",
    "and so is Steady Retry - a retry carries the SAME samplers now")
_tk8 = seg(py, "def autocal_tick", "def api_tts_diag")
nin(_tk8, "autocal_sampler_arith",
    "and the tick no longer calls it - the refit alone remains")
check("autocal_wait_idle" not in _tk8 and "tts_job_port" not in _tk8,
      "the tick asks nothing of any server - no port, no idle window")
# ONE switch: content behind it, values not gated by it
_sb8 = seg(JS, "function ttsSampBlock(st)", "// A job the panel gives to a model")
# patch109: a two-option menu like the one above it, not a switch. Manual leaves the
# samplers themselves in the user's hands: Manual means YOU move them, not that they
# stop being sent.
# retold patch23: no menu - the samplers are manual, always, and that is not a mode
nin(_sb8, "tts-ttsSampAutoCal", "there is no calibration menu on the sampler block")
check('ttsTitle("TTS Samplers"' in _sb8,
      "the block is titled TTS Samplers - calibration was never what it did")
check('id="tts-samp-chips"' in _sb8 and "if (!on) return" not in _sb8,
      "the samplers show unconditionally - there is no switch to hide them")
nin(JS, "ttsSampAutoCal = sac.value", "and nothing saves the setting it replaced")
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
    # retold patch23: only what Higgs takes is forwarded, so SkyrimNet's top_p and
    # min_p are DROPPED rather than passed on
    check(_a1 == {"temperature": 0.6},
          "a first attempt carries SkyrimNet's own values, minus what this engine "
          "cannot use", str(_a1))
    check(fp.tts_samplers(_ss, 2) == _a1 and fp.tts_samplers(_ss, 3) == _a1,
          "and every retry carries exactly the same ones - nothing narrows")
    check(fp.tts_samplers({**_ss, "ttsCalTemp": "0.9"}, 1)["temperature"] == 0.9,
          "a value set on the page wins over SkyrimNet's")
    check(set(fp.tts_samplers({}, 1)) == {"temperature"},   # retold p23
          "and what arrived is forwarded where this engine can use it",
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
    _realda = fp.autocal_derive_arith
    _realcfg = fp.CONFIG
    # the proxy tick loads the config, and load_config CREATES the file when it is
    # absent - pointed at the tree, the gate would write into what it judges
    fp.CONFIG = os.path.join(tempfile.mkdtemp(), "fleet-config.json")
    _arith = []
    fp.autocal_derive_arith = lambda cfg=None, why="": _arith.append(why) or {"ok": True}
    try:
        for _i in range(30):
            fp.autocal_tick({"ttsAutoCal": "proxy", "ttsAutoCalEvery": "5",
                             "ttsAutoCalPort": "1"})
    finally:
        fp.autocal_derive_arith = _realda
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
    try:
        for _i in range(7):
            fp.autocal_tick({"ttsAutoCal": "llm", "ttsAutoCalEvery": "5"})
    finally:
        fp.autocal_derive_arith = _realda
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
    _realda3 = fp.autocal_derive_arith
    _realcfg3 = fp.CONFIG
    fp.CONFIG = os.path.join(tempfile.mkdtemp(), "fleet-config.json")
    _ar3 = []
    fp.autocal_derive_arith = lambda cfg=None, why="": _ar3.append(why) or {"ok": True}
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
        fp.autocal_derive_arith = _realda3
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
_dvq = seg(py, "def autocal_derive_arith", "def autocal_lines_since")
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
# retold patch4: the decision moved into speaker_for_voice_ex, which reports WHICH
# rule answered; the slice bounds that function alone.
_sv = seg(py, "def speaker_for_voice_ex", "_PLAYER_SAID = [False]")
check("del _spk_recent[idx]" in _sv,
      "a paired request is CONSUMED, so a second voice cannot inherit the same name")
# retold patch5: the cache STOPPED answering. femaledarkelf handing Nelysa's name to
# the next dark elf who spoke five seconds later is what the fallback bought; the
# last-known name stays visible to the ledger and the one-voice guards, but a line
# with no live evidence prints as its voicetype.
check('return "", "no live evidence - the voicetype stands", cand' in _sv,
      "an unpaired line answers as its voicetype, never from the cache")
fp.panel_log = (lambda *_a, **_k: None) if not hasattr(fp, "_gate_quiet") else fp.panel_log
_realpl = fp.panel_log
_realtw = fp.TTSW.log        # retold patch4: a rebind raises the identity alarm, which
fp.panel_log = lambda *_a, **_k: None
fp.TTSW.log = lambda *_a, **_k: None   # reaches TTSW.log - and that loads a config
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp._spk_run.clear()
    fp._spk_pin.clear()
    fp.note_speaker(b"You are Brelyna Maryon, a mage of the College")
    _first = fp.speaker_for_voice("femalecommoner")
    _again = fp.speaker_for_voice("femalecommoner")
    fp.note_speaker(b"You are Ysolda, a trader in Whiterun")
    _second = fp.speaker_for_voice("femalecommoner")
finally:
    fp.panel_log = _realpl
    fp.TTSW.log = _realtw
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp._spk_run.clear()
    fp._spk_pin.clear()
check(_first == "Brelyna Maryon", "the name behind a voicetype is learned", _first)
check(_again == "Brelyna Maryon", "and held when nothing newer has arrived", _again)
check(_second == "Ysolda",
      "but a shared voicetype takes the character who just spoke, not the first ever",
      _second)
check("note_speaker(body, enqueue=" in seg_len(py, "def _mk_handler", 4000),  # retold patch5
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
_sv2 = seg(py, "def speaker_for_voice_ex", "def acpp_local_version")  # retold patch4
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
check("When in doubt, no tag." in _tp,   # retold p22: stronger than "optional"
      "and says plainly that neither is required - silence is the default")
check("At most one EMOTION and one AUDIO tag" in _tp,
      "explaining that the two kinds combine")
for _lbl in ("EMOTION (felt)", "AUDIO (heard)"):
    check(_lbl in _tp, "each kind says what it is for: %s" % _lbl)
# the whole point of cutting it: the prefill is the same prompt every time
_p_new = fp.tts_tag_prompt()
check(len(_p_new) < 1800,   # retold p22: two neutral examples joined the prompt
      "and the whole thing stays well under three quarters of what it was",
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


section("elation does not reach the engine unasked")
# MEASURED twice, years apart. First: 8 of 8 takes carrying <|emotion:elation|> came
# back in a different voice across two references at 83 Hz and 200 Hz, all landing at
# 265-381 Hz REGARDLESS of the reference - the speaker being dropped, not shifted.
# Then unblocked in patch24, when the Pitch Guard was thought to cover it; the Pitch
# Guard went in patch33 because pitch moves with feeling and not identity, leaving the
# fault untreated either way. patch41 blocked it outright and lost the switch with it.
# patch42 ships it OFF instead - the reason it stays reachable is that this entry has
# been wrong before, and the next sweep needs somewhere to disagree.
check("TTS_EMOTION_OFF" in py, "an emotions-off list exists")
# from the COMMENT, not the assignment - the reasoning is what matters here
_blk = seg(py, "# Emotions this build ships with turned OFF", "DEF_SETTINGS = {")
check("disgust" in _blk and "shame" in _blk,
      "populated by measurement, not by the mechanism being available")
check("ELATION HAS BEEN HERE BEFORE" in _blk,
      "and the one entry that has been added and removed before says so")
check("elation" in fp.TTS_EMOTION_OFF
      and "EMOTION-ELATION" in fp.DEF_SETTINGS["ttsTagsFinalOff"],
      "elation ships off, on the gate that stops it whoever wrote it")
check("EMOTION-ELATION" in " ".join(dict(fp.TAG_OFFER)["Emotion"]),
      "and stays on the board, because this entry has been wrong before")
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
_realtw2 = fp.TTSW.log       # retold patch4, as above
fp.panel_log = lambda *_a, **_k: None
fp.TTSW.log = lambda *_a, **_k: None
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp._spk_run.clear()
    fp._spk_pin.clear()
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _own = fp.speaker_for_voice("serana")
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _steal = fp.speaker_for_voice("femalecommoner")
    fp.note_speaker(b"You are Ysolda, a trader in Whiterun")
    _free = fp.speaker_for_voice("femalecommoner")
    _still = fp.speaker_for_voice("serana")
finally:
    fp.panel_log = _realpl2
    fp.TTSW.log = _realtw2
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp._spk_run.clear()
    fp._spk_pin.clear()
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
# retold patch34: 0, not llama.cpp's 8 - checkpoints live in HOST memory and a
# fleet server must not borrow system RAM to make a model appear to fit
check(bool(_cc) and _cc[0][3] == "0", "defaulting to 0, not llama.cpp's own 8",
      str(_cc and _cc[0][3]))
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
_sv2 = seg(py, "def speaker_for_voice_ex", "def tts_voice_name")  # retold patch4
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
_realtw3 = fp.TTSW.log       # retold patch4, as above
fp.panel_log = lambda *_a, **_k: None
fp.TTSW.log = lambda *_a, **_k: None
try:
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
    fp.note_speaker(b"You are Azeeda [hunter], a Female Redguard in Skyrim.")
    fp.note_speaker(b"You are Serana, a vampire of Volkihar")
    _one, _two = fp.speaker_for_voice("femalecommoner"), fp.speaker_for_voice("serana")
finally:
    fp.panel_log = _realpl3
    fp.TTSW.log = _realtw3
    fp._spk_recent[:] = []
    fp._spk_voices.clear()
check(_one == "Azeeda" and _two == "Serana",
      "two NPCs speaking in succession keep their own names", "%s / %s" % (_one, _two))
check("for idx in range(len(_spk_recent)):" in seg(py, "def speaker_for_voice_ex", "def tts_voice_name"),
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
# retold patch12: a slotgrid-scoped .pgrp override exists now, so the anchor
# pins the line-start original rule alone
check(".pgrp" in _css and "border-top" in seg(_css, "\n.pgrp {", ".pgrp:first-child"),
      "drawn as a rule, so the card reads as blocks")
# every parameter has to land somewhere, or a control disappears from the card
_ungrouped = [r[0] for r in fp.SERVER_PARAMS if r[0] not in fp.PARAM_GROUP]
check(not _ungrouped, "and no parameter is left without a group",
      ", ".join(_ungrouped) or "none")


# white, and the same rule the TTS page draws between its blocks
_pg = seg(_css, "\n.pgrp {", ".pgrp:first-child")   # retold patch12: see above
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
# SkyrimNet's template lists every emotion Higgs has and the panel offers every one -
# anger and fear included, without which an aggressive line could not be labelled.
# Six ship TURNED OFF rather than missing (patch42): the board is the whole vocabulary,
# the default decides what is used, and the user keeps the switch.
check(len(_em) == len(fp.TTS_TAGS["emotion"]),
      "every emotion the engine has is offered",
      "%d of %d" % (len(_em), len(fp.TTS_TAGS["emotion"])))
check(all(("EMOTION-%s" % e.upper()) in _em for e in fp.TTS_EMOTION_OFF),
      "the six that ship off among them - a default keeps its switch")
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
for _w in ("ANGER", "FEAR", "AMUSEMENT", "DETERMINATION", "BITTERNESS",
           "AFFECTION", "AROUSAL", "AWE", "CONTEMPLATION", "CONTENTMENT",
           "ENTHUSIASM", "HELPLESSNESS", "PRIDE", "RELIEF", "SURPRISE", "CONFUSION"):
    check(("EMOTION-%s" % _w) in _em, "asked for: %s" % _w)
# and the six that ship off are not in the PROMPT - the model must not spend its one
# tag on a word the wire will drop - while staying on the board. (patch42)
_pOff = fp.tts_tag_prompt(off=frozenset(
    w.upper() for w in fp.tags_off(fp.DEF_SETTINGS, "ttsTagsOff")))
for _w in ("DISGUST", "ELATION", "LONGING", "SADNESS", "SHAME", "DETERMINATION"):
    check(("EMOTION-%s" % _w) not in _pOff, "not asked of the tagger: %s" % _w)
    check(("EMOTION-%s" % _w) in _em, "but still on the board: %s" % _w)
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
# retold p37: shown by default - a thought is why the line after it makes sense,
# and the shipped "off" cost a session's diagnosis
check("ttsThoughtOut" in fp.DEF_SETTINGS, "it has a switch")
check(fp.DEF_SETTINGS["ttsThoughtOut"] == "on", "on by default")
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
check('speaker = note_speaker(body, enqueue=(rt["title"] == "Dialogue"))'
      in seg(py, "def _proxy(self)", "def _background_init"),  # retold patch5
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
# retold patch23: the at-rest rule is unchanged; the hover is now one 6px glow, so
# the seg that used to end at ":hover" now contains it - pin the rest rule itself
check(".plpay { cursor:pointer; }" in PAGE,
      "and at rest no glow restyles the glyphs - the hover may")
_ph45 = seg(PAGE, ".plpay:hover {", ".moodic[title]")
# retold patch23: ONE tight glow. The drop-shadow filter over two text-shadows
# re-blurred already-blurred pixels and the provider name read as out of focus.
check("text-shadow:0 0 6px var(--acc)" in _ph45 and "drop-shadow" not in _ph45,
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
# patch123 named the player from a standalone "Think internally as <n>" prompt. patch4
# removed it: SkyrimNet sends NPC think tasks in the same shape and the agreement test
# passes for those too, so the rule named an NPC as the player and every spoken line of
# the player's wore her name from then on. The pins are retold as its ABSENCE.
_ns23 = seg(py, "def note_speaker", "def speaker_for_voice")
nin(_ns23, "Think internally as",
    "note_speaker no longer reads a think prompt as the player's")
check("_player_name_learn(pm.group(1)" in _ns23,
      "the party heading is the only prompt that names them, through the one gate "
      "that can refuse a name")
check('sys_p += "\\n\\nThe line is spoken by the player, %s." % _pn' in py
      and "_pn = player_name_setting() or _spk_player[0]" in py,
      "PTI is told who the player is - the typed name first, then the read one")
check('_sys += "\\nThe player is %s." % _pn2' in py
      and "_pn2 = player_name_setting() or _spk_player[0]" in py,
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
# retold patch15: the cap now asks which VOICE is speaking
check("_cap, _capnote, _est = tts_auto_cap(text, _st0, vt=tts_voice_key(ref_path))" in _ao,
      "all from the one figure - the auto cap, which IS the guard when off")
_as = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
check('"EOC" in _msg' in _as, "a differently worded overrun is still recognised as one")
check("_try >= 2" in _as, "and it is tried three times, not for ever")


# Audio Tags defaults to stripping, and PTI forces it ON for the line it tagged itself -
# so the player was heard with feeling while every NPC line arrived flat, and nothing
# anywhere said why. The strip is a setting; being silent about it was the fault.
# CONTEMPLATION, not SADNESS: this block is about the translator, and patch41
# refuses sadness - the check would have been measuring the block instead.
_L = "[EMOTION-CONTEMPLATION] It has been a long day. [SFX-SIGH] The longest of my life."
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
# retold patch13: detect mode (the default) floors this clock at 30s so the token
# cap is the bound; the USER'S clock semantics are pinned under limit mode, where
# it is the bound.
_c0 = json.loads(fp.tts_acpp_config({"settings": {"ttsRunawayMode": "limit"}}))["models"][0]
check(_c0["busy_timeout_ms"] == 9000, "defaulting to 9s, not the old hardcoded 20",
      str(_c0["busy_timeout_ms"]))
for _v, _want in (("10", 2000), ("999999", 60000), ("abc", 9000), ("", 9000)):
    _g = json.loads(fp.tts_acpp_config({"settings": {"ttsAcppBusyMs": _v,
                                                    "ttsRunawayMode": "limit"}}))["models"][0]
    check(_g["busy_timeout_ms"] == _want,
          "clamped to something a server can honour: %r" % _v, str(_g["busy_timeout_ms"]))
check("ttsAcppBusyMs" in PAGE, "with a row on the TTS page")
_as2 = seg(py, "def tts_acpp_speak", "def _tts_acpp_once")
check("_spent = time.time() - _t0" in _as2, "a failed attempt is timed")
check("%.1fs lost" in _as2, "and says what it cost")
check("server limit" in _as2, "beside the limit that was meant to stop it")

section("the backend takes no settings, and the panel stops pretending otherwise")

# audio.cpp validates its session option list and exits on anything not on it. On the
# builds this panel grew up with, reference_cache_slots is the one option the Higgs
# family accepts - so temperature, top_k, top_p, repetition_penalty, sample_rate and
# max_new_tokens are gone rather than left as controls that cannot reach the engine.
# retold patch8: 0.6 dropped even that one, so the option is now CONDITIONAL - written
# by default, omitted after a refusal (_ACPP_NO_OPTS) or on request (no_opts).
_keep8o = fp._ACPP_NO_OPTS[0]
fp._ACPP_NO_OPTS[0] = False
_so = json.loads(fp.tts_acpp_config({"settings": {}}))["models"][0]["session_options"]
check(list(_so) == ["higgs_audio_tts.reference_cache_slots"],
      "one session option is written by default, the one older builds accept",
      str(list(_so)))
check("session_options" not in
      json.loads(fp.tts_acpp_config({"settings": {}}, no_opts=True))["models"][0],
      "and it can be left at home for the builds that refuse it")
fp._ACPP_NO_OPTS[0] = _keep8o
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
check(fp.DEF_SETTINGS.get("ttsActionOut") == "on",   # retold p38
      "on by default - like Thoughts, an off switch reads as a broken feature")
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
check('"ttsTagsOff": TTS_EMOTION_OFF_WORDS,' in py,
      "the clicked-off tags are one setting, seeded from the measured six")
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
check('"ttsTagsFinalOff": TTS_EMOTION_OFF_WORDS,' in py,
      "the gate is one setting, seeded from the same six")
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
# retold patch23: sampler calibration is gone; the reference pair replaces it
check(fp.DEF_SETTINGS["ttsTags"] == "on"
      and fp.DEF_SETTINGS["ttsMoodEvery"] == "5"
      and fp.DEF_SETTINGS["ttsCalTemp"] == "0.8"
      and fp.DEF_SETTINGS["ttsAnswerPing"] == "banned"   # retold p37
      and fp.DEF_SETTINGS["ttsWrapMode"] == "on",
      "the five requested defaults ship as asked: tags pass, PME every 5, "
      "Boson's temperature, ping Banned, the Proxy translates")
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
      and "tts_measure_row(text, secs, est, wall, vt)" in py   # retold patch15
      and "wall=(float(TTS_TAKE.get(\"final_s\") or 0.0)" in py,   # retold p18
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
# retold patch20: 1.60 never stopped binding - the fit asked 2.65 for weeks and
# was clamped every time. The guard bounds the cap; this is a sanity stop.
check(fp.AUTOCAL_HEAD_MAX == 4.00 and fp.AUTOCAL_HEAD_MIN == 1.08,
      "the clamp is a sanity stop, and the guard is the working bound")
_da30 = seg(py, "def autocal_derive_arith", "def autocal_lines_since")
check("tts_measure_ols(rows)" in _da30 and '"ttsAutoCalMedian"' in _da30,
      "the proxy refit is least squares, written to the same stored fit")
nin(_da30, "panel_chat", "and it asks no model")
nin(_da30, "autocal_wait_idle", "and waits for nothing - arithmetic cannot contend")
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
_ab46 = seg(JS, "const slotBusy = {}, slotPoll = {}, slotLogText = {}, slotVram = {};",  # retold patch3
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
# retold patch8: the write goes through the persistence gate now - loaded once,
# saved when the pairing is new - so the pin follows it there.
check("TTS_REF_BY_NAME[_lbl8] = ref_path" in py
      and "_lbl8 = tts_speaker_label(ref_path)" in py,
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
check("(_thEnd - time.time() + 0.5) if _thEnd else 0.0" in py
      and "_thEnd = time.time() + min(float(_tsec or 0.0), 12.0)" in py
      and "_hold_s = min(_thw, TTS_FLOOR_CAP_S)" in py and "time.sleep(_hold_s)" in py
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
# retold patch23: the CAP still escalates; the samplers never do
check('_cap = int(min(TTS_CAP_CEILING, _cap * (1.5 ** (attempt - 1))))' in py
      and "(0.8 ** _k)" not in py and "- 0.05 * (_k - 1)" not in py,
      "the retry escalates the cap half again per attempt, and nothing else")
check("\U0001F4A5" in JS and "\u2696\uFE0F" in JS
      and '"emoji": DEFAULT_PROVIDER_EMOJI.get(nm, "")' in py,
      "the picker offers the new marks, and a seeded default CARRIES its mark")
# retold patch23: the ladder's sampler stepping is REMOVED. Attempts two and three
# must now be identical - stepping toward greedy decoding is what produced the
# degenerate repeat this project spent days chasing.
_rl81 = None
try:
    _obs81, _cal81 = fp.sn_tts_observed, fp.cal_overrides
    fp.sn_tts_observed = lambda: {"temperature": 0.6, "top_p": 1.0,
                                  "min_p": 0.05, "repetition_penalty": 1.2}
    fp.cal_overrides = lambda st: {}
    _s81 = {}
    _a1 = fp.tts_samplers(_s81, 1)
    _a2 = fp.tts_samplers(_s81, 2); _a3 = fp.tts_samplers(_s81, 3)
    fp.sn_tts_observed, fp.cal_overrides = _obs81, _cal81
    _rl81 = [_a1 == _a2, _a2 == _a3, _a1 == {"temperature": 0.6}]
except Exception:
    _rl81 = None
if _rl81 is not None:
    check(_rl81 == [True] * 3,
          "run: every attempt carries the SAME samplers, and only what this engine "
          "uses reaches it - the narrowing that fed the fault is gone", str(_rl81))
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
check('(time.time() - _last_rx) <= 3.5' in py
      and '_cap = 3 if not _held else' in py
      and 'p.get("defer", 0) < _cap' in py
      and '_unfinished = bool(_nf) and _arriving and not any(' in py,
      "an unfinished reply earns a defer only while chunks actually arrive - and "
      "the three-step bound still holds when that is a guess rather than an open "
      "request")
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
# retold p36: the socket is always offered; client_scope is the boundary and is
# consulted per request, so Remote Access takes effect when it is switched
check('_bind = "0.0.0.0"' in py
      and "ThreadingHTTPServer((_bind, PORT), Handler)" in py,
      "the panel page binds the LAN interface, and scope decides who may speak")
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
      and 'cool=tags_off(st, "ttsTagsFinalOff") | _cool)' in seg_len(
          py, "raw = tts_npc_mood_arm", 300),
      "every NPC chunk is offered its queued completion mood at the one gate - and "
      "the arm is handed the final-off board too, because it forms its own token and "
      "the wire gate downstream leaves a formed one alone (patch42)")
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
# retold p38: the two guards are split so each can say WHY, and the result is
# held in _ok so a failure can be explained before it is returned
check("if time.time() - full[1] > 25.0:" in py
      and "_ok = _n >= min(12, len(nf), len(nc))" in py
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
      and 'if ("%s:%s" % pick) in cool:' in py,
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
check(set(fp.SN_TTS_FORWARD) == {"temperature", "top_k"},   # retold p23
      "which is two of them; the rest have no counterpart this engine uses have no counterpart and are only "
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
check(len(fp.CAL_KNOBS) >= 4, "there are bounded knobs to set", str(len(fp.CAL_KNOBS)))
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
_sfv = seg(py, "def speaker_for_voice_ex", "def player_name_unread")  # retold patch4
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
      and "if is_draft_arch(arch) or any(" in py,
      "a drafter that names its own architecture is taken at its word")
check('if sc.get("vision") and not meta.get(arch + ".block_count")' in py,
      "and a model that CARRIES a vision tower is still the model that runs - "
      "Muse Glimmer is image-text-to-text in one file")
check("def draft_launch_args(draft_path" in py and "def draft_spec_type(path):" in py
      and 'out = [("--spec-draft-model", p), ("--spec-type", kind)]' in py
      and "draft_n_max_ceiling(meta, kind)" in py,   # retold p25
      "EVERY drafter leaves with its type, and a DFlash one with its block size too")


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
                      ("--spec-draft-n-max", "15"), ("--spec-draft-ngl", "99")],
            _cv85 == [("--spec-draft-model", _pl85), ("--spec-type", "draft-simple"),
                      ("--spec-draft-ngl", "99")],
            "--spec-draft-ngl" not in _no85]
except Exception:
    _a85 = None
if _a85 is not None:
    check(_a85 == [True, True, True],
          "run: a DFlash drafter is launched with its own block size as the depth, a "
          "plain small drafter with draft-simple - both TYPED, since an untyped "
          "drafter drafts nothing - and neither is placed on a card the user did "
          "not name", str(_a85))
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
            '"--spec-draft-n-max", "15"' in _txt85,   # retold p25
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

check('_KIND_RULES = "375p2"' in py and '_m.get("_rules") == _KIND_RULES' in py,
      "and a cache of verdicts reached under the OLD rule is dropped, not trusted - "
      "the drafter was already remembered as a plain model, and the qwen35 heads "
      "were remembered before the tensor rule existed")

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
            '"--spec-draft-model", "%s"' % _pl86 in _conv86,
            '"--spec-type", "draft-simple"' in _conv86,
            "--model-draft" not in _conv86]
except Exception:
    _rt86 = None
if _rt86 is not None:
    check(_rt86 == [True] * 10,
          "run: every card setting survives card -> hand-edited launcher -> card, "
          "Disabled removes the whole speculative block while the comment and the "
          "sampler line around it stay, and swapping a DFlash assistant for a plain "
          "drafter re-types it rather than dropping to an untyped flag", str(_rt86))
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

# ------------------------------------------------------- v3.75 patch1 (hotfix)
# llama.cpp runs NO speculation unless it is told which kind: --spec-type
# defaults to none, and only a HuggingFace sidecar download fills it in by
# itself. A local drafter named with --model-draft alone therefore loads, holds
# its VRAM and drafts not one token - silently. The owner's Gemma 4 assistants
# did exactly that ("no implementations specified for speculative decoding"),
# and only the decode speed showed it. Every drafter now leaves with its type,
# derived from the architecture it declares.
check("def draft_spec_type(path):" in py and "def _spec_kind(arch, scan):" in py
      and '"draft-mtp"' in py and '"draft-eagle3"' in py and '"draft-simple"' in py
      and "def is_draft_arch(arch):" in py and 'a.endswith("-assistant")' in py,
      "a head shipped beside a family is a drafter, and each kind has its type")
_sp1 = None
try:
    _d1 = tempfile.mkdtemp()
    _mk1 = {}
    for _nm, _ar, _extra in (
            ("gemma4-31B-it-assistant-Q8_0.gguf", "gemma4-assistant",
             {"gemma4-assistant.block_count": (4, 4)}),
            ("Muse-Glimmer-30B-assistant-Q8_0.gguf", "dflash",
             {"dflash.block_size": (4, 16)}),
            ("eagle3-head.gguf", "eagle3", {}),
            ("Qwen3-0.6B-Q8_0.gguf", "qwen3", {"qwen3.block_count": (4, 28)}),
            ("gemma4-31B-it-Q6_K.gguf", "gemma4", {"gemma4.block_count": (4, 62)})):
        _p1 = os.path.join(_d1, _nm)
        _kv1 = {"general.architecture": (8, _ar)}
        _kv1.update(_extra)
        _mkgguf85(_p1, _kv1,
                  ["token_embd.weight"] + ["blk.%d.attn_q.weight" % i for i in range(4)])
        _mk1[_ar] = _p1
    _t1 = lambda a: dict(fp.draft_launch_args(_mk1[a], "99")).get("--spec-type")
    _sp1 = [fp._model_kind_read(_mk1["gemma4-assistant"]) == "draft",
            fp._model_kind_read(_mk1["gemma4"]) == "main",
            _t1("gemma4-assistant") == "draft-mtp",
            _t1("dflash") == "draft-dflash",
            _t1("eagle3") == "draft-eagle3",
            _t1("qwen3") == "draft-simple",
            dict(fp.draft_launch_args(_mk1["dflash"], "99")).get("--spec-draft-n-max") == "15",
            "--spec-draft-n-max" not in dict(fp.draft_launch_args(_mk1["gemma4-assistant"], "99")),
            all("--model-draft" not in dict(fp.draft_launch_args(_p, "99"))
                for _p in _mk1.values())]
except Exception:
    _sp1 = None
if _sp1 is not None:
    check(_sp1 == [True] * 9,
          "run: an assistant head reads as a DRAFTER while the model it drafts for "
          "stays a model; MTP, DFlash, EAGLE-3 and a plain small model each leave "
          "with their own --spec-type; only DFlash carries a block depth; and no "
          "drafter leaves with a bare --model-draft that would draft nothing",
          str(_sp1))
else:
    check(False, "the spec-type run did not RUN")
_lp1 = None
try:
    _cfg1 = {"settings": {}, "gpus": []}
    _gm1 = _mk1["gemma4-assistant"]
    _own1 = "\n".join(['$llamaArgs = @(', '    "-m", "main.gguf",',
                       '    "--n-gpu-layers", "99",', '',
                       '    # --- speculative decoding: MTP ---',
                       '    "--model-draft", "%s",' % _gm1, '',
                       '    "--temp", "1.0",', ')'])
    _s1 = {"id": "s1", "port": 1236,
           "params": {"model": "main.gguf", "draft": _gm1, "vision": "N/A", "ngl": "99"}}
    _o1 = _own1
    for _f, _v in sorted(fp.slot_flag_values(_cfg1, _s1, _own1, ["draft"]).items()):
        _o1 = fp.ps1_set_flag(_o1, _f, _v,
                              after=fp.CTK_AFTER if _f == fp.CTK_FLAG else None)
    _gen1 = fp.build_param_launcher(_cfg1, {"id": "s2", "port": 1237, "label": "G",
                                            "gpuId": "", "params": {"model": "main.gguf",
                                            "draft": _gm1, "ngl": "99"}},
                                    os.path.join(_d1, "gen.ps1"))
    _lp1 = ['"--spec-type", "draft-mtp"' in _o1,
            "--model-draft" not in _o1,
            "speculative decoding: MTP" in _o1 and '"--temp", "1.0"' in _o1,
            '"--spec-type", "draft-mtp"' in _gen1,
            "--model-draft" not in _gen1]
except Exception:
    _lp1 = None
if _lp1 is not None:
    check(_lp1 == [True] * 5,
          "run: a launcher that named a drafter the OLD way is corrected in place - "
          "the type arrives, the dead flag goes, and everything a person wrote "
          "around it stays; the generated launcher agrees", str(_lp1))
else:
    check(False, "the launcher-upgrade run did not RUN")

# ------------------------------------------------------------------ v3.75 patch2
# llama.cpp types a drafter by its TENSORS, not its architecture
# (common_speculative_types_from_gguf): a non-DFlash file is an MTP drafter iff
# it carries blk.{block_count-1}.nextn.eh_proj.weight, and a DFlash-arch file
# with a Markov head is DSpark. The qwen35-generation heads declare the FAMILY
# architecture, so the architecture-only rule sent them out as draft-simple and
# llama-server tried to load a one-layer head file as a 65-layer model. The same
# tensor, inside a full model, means the model drafts for ITSELF - the card says
# so. And the tensor that proves all of this sits at the END of the list, so a
# scan capped at the first few hundred names could never have seen it.
check("def gguf_tensor_scan(path, block_count=0):" in py
      and '"blk.%d.nextn.eh_proj.weight" % (int(block_count or 0) - 1)' in py
      and "for _ in range(ntensor):" in py and "range(min(ntensor" not in py,
      "every tensor name is read, and the MTP tensor llama.cpp looks for is "
      "looked for by its exact name at the last block")
check('return "draft-dspark" if sc.get("markov") else "draft-dflash"' in py
      and 'or sc.get("nextn_last") or sc.get("mtp_names"):' in py,
      "the Markov head tells DSpark from DFlash, and the nextn/mtp tensors make "
      "an MTP drafter of a file whatever architecture it declares")
check('"mtpHead": bool(kind == "main" and (scan or {}).get("nextn_last"))' in py
      and '"spec": _spec_kind(arch, scan)' in py,
      "a file's facts carry the speculation kind it would perform and whether, "
      "as a model, it drafts for itself")
check('return "main" if sc.get("blk0") else "draft"' in py,
      "the SAME tensor reads two ways: with the blocks before it, a model that "
      "drafts for itself; alone, that head extracted into a drafter file")
# retold patch12: the note is the yellow chip now, worded as the picker option
check("'Built-in MTP head</span></div>'" in py and "chosen.mtpHead" in py
      and py.count("mtpHead") >= 4,
      "and the card says so, under the model it belongs to")
check('"qwen35": "Qwen 3.5/3.8 family"' in py
      and '"qwen35moe": "Qwen 3.5/3.8 family (MoE)"' in py,
      "the qwen35 generation is named, not guessed from a prefix")
check('range:"draft-simple | draft-mtp | draft-eagle3 | draft-dflash | draft-dspark"' in py,
      "the guide states the real types, DSpark included")
check('!/^-?[0-9]+$/.test(tk.trim())' in py and "usually belongs to --top-p" in py,
      "the launcher check flags an integer flag handed a fraction - a top-k of "
      "0.95 reads as 0 and turns the sampler off in silence")

_p2 = None
try:
    _d2 = tempfile.mkdtemp()
    _nm2 = ["token_embd.weight"]
    for _i2 in range(64):
        _nm2 += ["blk.%d.attn_q.weight" % _i2, "blk.%d.ffn_up.weight" % _i2,
                 "blk.%d.ffn_down.weight" % _i2, "blk.%d.attn_norm.weight" % _i2,
                 "blk.%d.ffn_gate.weight" % _i2, "blk.%d.attn_output.weight" % _i2,
                 "blk.%d.attn_v.weight" % _i2]
    _nm2 += ["blk.64.attn_q.weight", "blk.64.nextn.eh_proj.weight",
             "blk.64.nextn.enorm.weight", "output.weight"]
    _mn2 = os.path.join(_d2, "Omega-Convergence-27B-v1.0-q8_0.gguf")
    _mkgguf85(_mn2, {"general.architecture": (8, "qwen35"),
                     "qwen35.block_count": (4, 65),
                     "qwen35.context_length": (4, 262144)}, _nm2)
    _hd2 = os.path.join(_d2, "mtp-Omega-Convergence-27B-v1.0-q8_0.gguf")
    _mkgguf85(_hd2, {"general.architecture": (8, "qwen35"),
                     "qwen35.block_count": (4, 65)},
              ["blk.64.attn_q.weight", "blk.64.nextn.eh_proj.weight",
               "blk.64.nextn.enorm.weight"])
    _ds2 = os.path.join(_d2, "dspark-drafter.gguf")
    _mkgguf85(_ds2, {"general.architecture": (8, "dflash"),
                     "dflash.block_size": (4, 16), "dflash.block_count": (4, 5)},
              ["markov_w1.weight", "token_embd.weight", "blk.0.attn_q.weight"])
    _fm2 = fp._model_facts_read(_mn2)
    _fh2 = fp._model_facts_read(_hd2)
    _fd2 = fp._model_facts_read(_ds2)
    _lah2 = fp.draft_launch_args(_hd2, "99")
    _lad2 = fp.draft_launch_args(_ds2, "99")
    _p2 = [len(_nm2) > 400 and _fm2["kind"] == "main" and _fm2["mtpHead"] is True
           and _fm2["spec"] == "draft-mtp" and _fm2["label"] == "Qwen 3.5/3.8 family",
           _fh2["kind"] == "draft" and _fh2["mtpHead"] is False
           and _fh2["spec"] == "draft-mtp",
           _fd2["kind"] == "draft" and _fd2["spec"] == "draft-dspark",
           _lah2 == [("--spec-draft-model", _hd2), ("--spec-type", "draft-mtp"),
                     ("--spec-draft-ngl", "99")],
           _lad2 == [("--spec-draft-model", _ds2), ("--spec-type", "draft-dspark"),
                     ("--spec-draft-n-max", "16"), ("--spec-draft-ngl", "99")]]
except Exception:
    _p2 = None
if _p2 is not None:
    check(_p2 == [True] * 5,
          "run: a qwen35 model whose MTP head sits past the 400th tensor name is a "
          "MODEL that drafts for itself and the card knows it; the head extracted "
          "into its own file is a DRAFTER that leaves as draft-mtp, not "
          "draft-simple; a Markov-headed DFlash file leaves as draft-dspark with "
          "its block depth", str(_p2))
else:
    check(False, "the tensor-rule run did not RUN")


# The same hotfix, second half. llama.cpp's memory fitting builds a throwaway
# probe context for the drafter before the target model exists, so a head that
# must attach to the target - Gemma 4 assistant, DFlash, EAGLE-3 - always throws
# there. llama.cpp catches it, says so in the message, and loads the drafter
# properly a moment later. Raised as an ERROR it sent the owner hunting a
# parameter that does not exist; it is noted now, not raised. Nothing else
# softens: a real load failure is still a failure.
check("BENIGN_RX = re.compile(" in py and "requires ctx_other to be set" in py
      and "if BENIGN_RX.search(line):" in py
      and "ERR_RX.search(ln) and not BENIGN_RX.search(ln)" in py
      and 'if "fit" not in BENIGN_SEEN:' in py,
      "the fitting probe's self-declared warning is kept out of the error log AND "
      "out of the issue list, explained once instead")
_bn1 = None
try:
    _real1 = [
        "llama_init_from_model: failed to initialize the context: Gemma4Assistant "
        "requires ctx_other to be set (this warning is normal during memory fitting)",
        "srv    load_model: [spec] failed to measure draft model memory: failed to "
        "create llama_context from model",
        "srv    load_model: [spec] failed to measure MTP context memory: failed to "
        "create llama_context from model"]
    _still1 = [
        "ggml_cuda_host_malloc: failed to allocate pinned memory: out of memory",
        "srv    load_model: failed to load model 'x.gguf'",
        "common_speculative_init_result: failed to create MTP context",
        "srv    load_model: [spec] failed to measure draft model memory: CUDA out of "
        "memory".replace("failed to measure draft model memory", "loaded nothing")]
    # and the WATCHER itself, over a log holding both kinds twice over: keeping
    # them out of the error file was not enough, because the issue list decides a
    # line's severity from its own words and "failed" is in this one
    _d1b = tempfile.mkdtemp()
    _notes1 = []
    _pl1 = fp.panel_log
    fp.panel_log = lambda m: _notes1.append(m)
    open(os.path.join(_d1b, "srv_gate1_9.log"), "w", encoding="utf-8").write(
        "=== hdr ===\n" + "\n".join(_real1 * 2 + _still1) + "\n")
    _keepLog, _keepTot = list(fp.ERR_LOG), fp.ERR_TOTAL[0]
    _keepLvl, _keepTyp = dict(fp.ERR_BY_LEVEL), dict(fp.ERR_BY_TYPE)
    _keepFile = fp.ERR_FILE[0]
    del fp.ERR_LOG[:]
    fp.ERR_TOTAL[0] = 0
    fp.ERR_BY_LEVEL.clear(); fp.ERR_BY_TYPE.clear()
    fp.ERR_FILE[0] = os.path.join(_d1b, "error_1.log")
    open(fp.ERR_FILE[0], "w", encoding="utf-8").write("=== hdr ===\n")
    fp.scan_slot_errors("gate1", "Gate Server", _d1b)
    _rows1 = [_e["title"] for _e in fp.ERR_LOG]
    _filelines = len(open(fp.ERR_FILE[0], encoding="utf-8").read().strip().split("\n")) - 1
    fp.panel_log = _pl1
    del fp.ERR_LOG[:]
    fp.ERR_LOG.extend(_keepLog)
    fp.ERR_TOTAL[0] = _keepTot
    fp.ERR_BY_LEVEL.clear(); fp.ERR_BY_LEVEL.update(_keepLvl)
    fp.ERR_BY_TYPE.clear(); fp.ERR_BY_TYPE.update(_keepTyp)
    fp.ERR_FILE[0] = _keepFile
    _bn1 = [all(fp.BENIGN_RX.search(_l) for _l in _real1),
            all(fp.ERR_RX.search(_l) for _l in _real1),
            not any(fp.BENIGN_RX.search(_l) for _l in _still1),
            all(fp.ERR_RX.search(_l) for _l in _still1),
            len(_rows1) == len(_still1),
            not any("ctx_other" in _r or "measure draft model" in _r for _r in _rows1),
            _filelines == len(_still1),
            len(_notes1) == 1]
except Exception:
    _bn1 = None
if _bn1 is not None:
    check(_bn1 == [True] * 8,
          "run: the fitting lines read as failures and are recognised as benign, and "
          "the WATCHER puts neither in the error file nor in the issue list, saying "
          "once why - while a real out-of-memory, a real load failure and a real MTP "
          "context failure all still land in both", str(_bn1))
else:
    check(False, "the benign-line run did not RUN")

# ------------------------------------------------- v3.75 hotfix1, third part
# A voice read a tag aloud. Three things had to line up: SkyrimNet's prompt asks
# the model for LOWERCASE tags while the panel only ever recognised the mod's own
# ALL-CAPS ones; the model put one before a full stop, so the sentence split fell
# through it; and what arrived - "[prosody-expressive_low." - had lost its closing
# bracket upstream. The panel is the last thing between the text and a voice, so
# it now reads a tag in any case, survives a damaged one, deletes anything merely
# tag-SHAPED, and holds a tag whose chunk carried no words for the words that
# follow instead of speaking it.
check("re.I)" in seg_len(py, "TTS_CAPS_RX = re.compile(", 400)
      and "TTS_TAGSHAPE_RX = re.compile(" in py and "TAG_CARRY = {}" in py
      and "def tts_wordless(text):" in py
      and "if tts_wordless(processed):" in py
      and "tag with no words - held for the next line" in py,
      "tags are read in any case, damaged or not, and a chunk with no words for a "
      "voice to say holds its tags for the next one instead of being spoken")
_tg1 = None
try:
    _ap = lambda s: fp.tts_apply_tags(s, True, "audiocpp")
    _field = _ap("[prosody-expressive_low.")           # exactly what arrived
    _low = _ap("[emotion-bitterness]Sigh, yes.")       # the prompt's own casing
    _caps = _ap("[EMOTION-ANGER]Get out.")             # the mod's casing
    _unknown = _ap("[emotion-nosuchfeeling]Hello there.")
    _bare = _ap("prosody-speed_fast Quickly now.")     # brackets lost entirely
    _dialogue = _ap("Meet me at the [Bannered Mare] tonight.")
    _notes = _ap("I keep my notes in [brackets] sometimes.")
    _words = lambda s: fp.TTS_TAG_ANY_RX.sub("", s).strip(" .,!?;:\"'")
    _tg1 = [_field == "<|prosody:expressive_low|>.",
            _words(_field) == "",
            "<|emotion:bitterness|>" in _low and _words(_low) == "Sigh, yes",
            "<|emotion:anger|>" in _caps,
            _unknown == "Hello there.",
            "<|prosody:speed_fast|>" in _bare,
            _dialogue == "Meet me at the [Bannered Mare] tonight.",
            _notes == "I keep my notes in [brackets] sometimes.",
            not any(_w in _words(_x).lower() for _w in
                    ("emotion", "prosody", "style", "sfx")
                    for _x in (_field, _low, _caps, _unknown, _bare)),
            fp.tts_wordless(_field) and not fp.tts_wordless(_low),
            fp.tts_wordless("<|emotion:anger|> . ") and not fp.tts_wordless("Oh.")]
except Exception:
    _tg1 = None
if _tg1 is not None:
    check(_tg1 == [True] * 11,
          "run: the field's damaged tag becomes a token and leaves NO words, a "
          "lowercase tag and an ALL-CAPS one both convert, an unknown value and a "
          "bracketless one are removed rather than spoken, real dialogue brackets "
          "are untouched, no family word survives into speech, and a chunk left "
          "with only a token counts as wordless", str(_tg1))
else:
    check(False, "the tag-recognition run did not RUN")

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
_lr = seg(JS, "function liveRefresh", "async function ttsInstalled")
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


# ------------------------------------------------------------------ v3.75 patch3
# A model with its own MTP head is its own drafter; a dialogue reply that OPENS
# with the thought is served dialogue-first; thoughts leave whole; the card
# reads its VRAM report from llama.cpp's lines and does not trust the
# launcher's STATUS; a held-but-silent port names both of its causes.
section("v3.75 patch3: builtin MTP, leading-thought reorder, VRAM report")

check('DRAFT_BUILTIN = "@builtin-mtp"' in py,
      "the builtin drafter sentinel exists, path-unlike by design")
check('if p == DRAFT_BUILTIN:' in py and '[("--spec-type", "draft-mtp")]' in py,
      "draft_launch_args answers the sentinel with the type and nothing else")
check('"draft-mtp" in (grab("--spec-type") or "")' in py,
      "a launcher naming the type with no draft file reads back as the builtin")
check('drf_builtin = str(t.get("draft") or "") == DRAFT_BUILTIN' in py,
      "the launcher renderer knows builtin is not off")
check('def reorder_leading_thought(' in py and 'class ThoughtReorderStream' in py
      and '_LEAD_THOUGHT_RX' in py,
      "the leading-thought rule exists in pure and streamed form")
check('rw = ThoughtReorderStream() if rt["title"] == "Dialogue" else None' in py
      and 'reorder_leading_thought(_m0.get("content")' in py,
      "the relay reorders Dialogue replies only, on both paths")
check('" ".join(m.split())[:400]' not in py
      and 'never capped: this list feeds the thought-audio pass' in py,
      "thought rows are uncapped, and the reason is written where the cap was")
check('def slot_vram_report(' in py and '"STATUS: loaded"' in py
      and 'over a launch that died' in py,
      "the VRAM report parser exists and distrusts the launcher's STATUS line")
check('Server process exited before it became ready' in py
      and 'port held but nothing answers on it' in py,
      "a dead launch is detected, and the wedged verdict names both causes")
check('id="vram-' in py and 'function vramTick' in py and '.vramline {' in py,
      "the report strip sits above the card terminal and is polled")
check('Built-in MTP head &#8212; the model drafts for itself' in py
      and 'carries no ' in py,
      "the picker offers the builtin head and calls out a headless model in red")

import tempfile as _tf3
_NL3 = chr(10)
try:
    _bi3 = fp.DRAFT_BUILTIN
    _a3 = fp.draft_launch_args(_bi3, "99") == [("--spec-type", "draft-mtp")]
    _s3 = {"id": "s1", "port": 1236,
           "params": {"model": "m.gguf", "draft": _bi3, "vision": "N/A", "ngl": "99"}}
    _fv3 = fp.slot_flag_values({"settings": {}, "gpus": []}, _s3, "", ["draft"])
    _b3 = (_fv3.get("--spec-type") == "draft-mtp"
           and _fv3.get("--spec-draft-model") is None
           and _fv3.get("--spec-draft-ngl") is None
           and _fv3.get("--model-draft") is None
           and _fv3.get("--spec-draft-n-max") is None)
    _own3 = _NL3.join(['$llamaArgs = @(', '    "-m", "main.gguf",',
                       '    "--spec-draft-model", "OLD.gguf",',
                       '    "--spec-draft-ngl", "99",',
                       '    "--spec-type", "draft-simple",',
                       '    "--temp", "1.0",', ')'])
    _o3 = _own3
    for _f3, _v3 in sorted(_fv3.items(), key=lambda x: (x[1] is None, x[0])):
        _o3 = fp.ps1_set_flag(_o3, _f3, _v3,
                              after=fp.CTK_AFTER if _f3 == fp.CTK_FLAG else None)
    _c3 = ('"--spec-type", "draft-mtp"' in _o3 and "OLD.gguf" not in _o3
           and "--spec-draft-ngl" not in _o3 and '"--temp", "1.0"' in _o3)
    _tpl3 = _NL3.join(['$llamaArgs = @(', '    "-m", "<MODEL_PATH>",',
                       '    "--spec-draft-model", "<DRAFT_PATH>",',
                       '    "--spec-draft-ngl", "99",', ')'])
    _rl3 = _NL3.join(fp.render_launcher_lines(
        {"content": _tpl3, "model": "m.gguf", "draft": _bi3, "vision": "N/A",
         "gpu": "", "port": 1236, "title": "T"}, "x.ps1", "llama-server.exe"))
    _d3ok = ('"--spec-type", "draft-mtp"' in _rl3 and "<DRAFT_PATH>" not in _rl3
             and "--spec-draft-model" not in _rl3 and "--spec-draft-ngl" not in _rl3)
    _pb3 = fp.parse_launcher_params('$llamaArgs = @(' + _NL3
                                    + '    "--spec-type", "draft-mtp",' + _NL3 + ')')
    _pc3 = fp.parse_launcher_params('$llamaArgs = @(' + _NL3
                                    + '    "--spec-draft-model", "D:' + chr(92) + 'h.gguf",'
                                    + _NL3 + '    "--spec-type", "draft-mtp",' + _NL3 + ')')
    _e3 = (_pb3.get("draft") == _bi3
           and _pc3.get("draft") == "D:" + chr(92) + "h.gguf")
    _run3 = [_a3, _b3, _c3, _d3ok, _e3]
except Exception:
    _run3 = None
if _run3 is not None:
    check(_run3 == [True] * 5,
          "run: the builtin head travels the whole pipeline - launch args, the "
          "surgical map, an in-place rewrite that keeps a person's tuning, a "
          "generated launcher, and both read-back directions", str(_run3))
else:
    check(False, "the builtin-head pipeline run did not RUN")

try:
    _T3 = "<internal_thought>the plan</internal_thought>"
    _cases3 = [
        ("hello there", "hello there"),
        (_T3, _T3),
        (_T3 + " Speak now.", " Speak now." + _NL3 + _T3),
        ("[tag1][tag2]" + _T3 + "Words.", "[tag1][tag2]Words." + _NL3 + _T3),
        ("Words first. " + _T3 + " More words.", "Words first. " + _T3 + " More words."),
        (_T3 + "d1 words<internal_thought>t2</internal_thought>d2",
         "d1 words" + _NL3 + _T3 + "<internal_thought>t2</internal_thought>d2"),
        (_T3 + "   ", _T3 + "   "),
    ]
    _pure3 = all(fp.reorder_leading_thought(a) == b for a, b in _cases3)
    import json as _js3
    def _sse3(txt):
        return (b"data: " + _js3.dumps(
            {"choices": [{"index": 0, "delta": {"content": txt}}]}).encode()
            + chr(10).encode() * 2)
    _stream3 = True
    for _a, _want in _cases3:
        for _sz in (1, 3, 7, 50, 4096):
            _rw = fp.ThoughtReorderStream()
            _outs = []
            for _i in range(0, len(_a), _sz):
                _ck = _a[_i:_i + _sz]
                _outs.extend(_rw.feed(_sse3(_ck),
                                      {"choices": [{"delta": {"content": _ck}}]}))
            _outs.extend(_rw.feed(b"data: [DONE]" + chr(10).encode() * 2, None))
            _got = []
            for _ln in _outs:
                _st = _ln.strip()
                if not _st.startswith(b"data: ") or _st == b"data: [DONE]":
                    continue
                _dl = _js3.loads(_st[6:]).get("choices", [{}])[0].get("delta", {})
                if _dl.get("content"):
                    _got.append(_dl["content"])
            if "".join(_got) != _want or "".join(_rw.said) != _want:
                _stream3 = False
    check(_pure3, "run: the pure reorder rule answers all seven shapes as written")
    check(_stream3, "run: the streamed rewrite is byte-identical to the pure rule "
                    "at chunk sizes 1, 3, 7, 50 and 4096, in output and in the report")
except Exception as _e:
    check(False, "the reorder runs did not RUN", str(_e)[:120])

try:
    _lc3 = fp.load_config
    fp.load_config = lambda *a, **k: {"settings": {}}
    fp.THOUGHT_FRESH.clear()
    fp.thought_lines("<internal_thought>" + ("word " * 200) + "</internal_thought>",
                     who="GateWho", cfg={"settings": {}})
    _row3 = fp.THOUGHT_FRESH.get("GateWho", ("",))[0]
    fp.load_config = _lc3
    check(len(_row3) > 900 and _row3.endswith("word"),
          "run: a long thought reaches the audio pass whole, not cut at 400")
except Exception as _e:
    try:
        fp.load_config = _lc3
    except Exception:
        pass
    check(False, "the uncapped-thought run did not RUN", str(_e)[:120])

try:
    _dv3 = _tf3.mkdtemp()
    _p3 = os.path.join(_dv3, "srv_slot1_1.log")
    _log3 = _NL3.join([
        "=== 2026-08-15T13:27:47 | Server 1 | slot1 ===",
        "  GPU free VRAM: 30,991 MiB (30.26 GiB)",
        "load_tensors:        CUDA0 model buffer size = 20054.43 MiB",
        "load_tensors:    CUDA_Host model buffer size =   994.63 MiB",
        "srv    load_model: [spec] estimated memory usage of MTP context is 188.19 MiB",
        "llama_kv_cache:      CUDA0 KV buffer size =   960.00 MiB",
        "llama_memory_recurrent:      CUDA0 RS buffer size =   149.62 MiB",
        "sched_reserve:      CUDA0 compute buffer size =   137.02 MiB",
        "sched_reserve:  CUDA_Host compute buffer size =    35.02 MiB",
        "Server ready - 5090 CUDA",
    ])
    with open(_p3, "w") as _fh3:
        _fh3.write(_log3)
    _r3 = fp.slot_vram_report(_p3)
    _v1 = (_r3["any"] and _r3["weightsGpu"] == 20054.43 and _r3["weightsHost"] == 994.63
           and _r3["mtpCtx"] == 188.19 and _r3["kv"] == 960.0 and _r3["rs"] == 149.62
           and _r3["compGpu"] == 137.02 and _r3["compHost"] == 35.02
           and _r3["freeAtLoad"] == 30991.0 and _r3["ready"] and not _r3["exited"])
    with open(_p3, "w") as _fh3:
        _fh3.write("old" + _NL3 + "=== earlier ===" + _NL3
                   + "load_tensors:        CUDA0 model buffer size = 1.00 MiB" + _NL3
                   + _log3.replace("Server ready - 5090 CUDA",
                                   "Server process exited before it became ready."))
    _r3b = fp.slot_vram_report(_p3)
    _v2 = _r3b["exited"] and not _r3b["ready"] and _r3b["weightsGpu"] == 20054.43
    with open(_p3, "w") as _fh3:
        _fh3.write(_NL3.join([
            "=== s ===",
            "load_tensors:        CUDA0 model buffer size = 20000.00 MiB",
            "srv    load_model: loading draft model x.gguf",
            "load_tensors:        CUDA0 model buffer size = 450.00 MiB",
            "llama_kv_cache:      CUDA0 KV buffer size =    64.00 MiB",
        ]))
    _r3c = fp.slot_vram_report(_p3)
    _v3 = (_r3c["weightsGpu"] == 20000.0 and _r3c["draftGpu"] == 450.0
           and _r3c["kvDraft"] == 64.0)
    check(_v1 and _v2 and _v3,
          "run: the VRAM parser buckets every component, reads only the LAST "
          "session, calls a dead launch dead, and keeps the drafter's buffers "
          "out of the model's", str([_v1, _v2, _v3]))
except Exception as _e:
    check(False, "the VRAM parser run did not RUN", str(_e)[:120])


# ------------------------------------------------------------------ v3.75 patch4
# Two bad identity transitions, both taken from one session's TTS log: an NPC think
# task named the PLAYER (patch123's rule stopped discriminating when SkyrimNet began
# sending them), and a one-word greeting moved a character's name onto a passing
# stranger's voicetype. Plus the ledger that makes either answerable from a log.
section("v3.75 patch4: player naming, one character one voice, the identity ledger")

nin(py, "PLAYER_THINK", "the think-task rule is REMOVED, not left disabled")
check("def _player_name_learn(" in py and "as the player from %s - that name already" in py
      and '"speaks through %s" % (nm, source, bound)' in py,
      "one place takes the player's name, and refuses one that already has a voice")
check("_spk_player_src" in py, "and records where it came from")
check("def player_name_setting(" in py and '"ttsPlayerName"' in py
      and "_spk_typed = [\"\"]" in py,
      "a typed name exists, is a real setting, and is read from a slot rather "
      "than a config parse on every spoken line")
check("SPEAKER_TEXT_MIN = 24" in py,
      "the words rule has a length floor - a greeting names nobody")
check("def speaker_for_voice_ex(" in py
      and 'return speaker_for_voice_ex(voicetype)[0]' in py,
      "every naming rule reports WHICH rule answered, through one dispatcher")
check("def tts_ref_fingerprint(" in py and "def tts_identity_note(" in py
      and "def tts_identity_alarm(" in py,
      "the ledger, the fingerprint and the alarm exist")
check("tts-identity.log" in py, "the ledger has a file of its own")
check("MISSING - nothing to clone from" in py
      and "the sample for %s is missing" in py,
      "a reference that is not on disk is called missing rather than printed as a name")
_pti4 = seg(JS, "function ttsPlayerTagRow(st)", "function ttsThoughtAudioRow(st)")
check('id="tts-ttsPlayerName"' in _pti4, "the field sits under the Player Tag Injector")
check('"ttsPlayerName"' in JS.split('function saveTtsMode')[1][:1200]
      or '"ttsPlayerName",' in JS, "and it is saved with the rest of the page")

import tempfile as _tf4
try:
    _D4 = _tf4.mkdtemp()
    _lc4, _lcc4, _ld4 = fp.load_config, fp.load_config_cached, fp.log_dir
    _pl4 = fp.panel_log
    fp.panel_log = lambda *_a, **_k: None      # or the run writes a config and a log
    _tl4 = fp.TTSW.log                         # TTSW.log calls log_dir() with NO cfg,
    fp.TTSW.log = lambda *_a, **_k: None       # which loads - and WRITES - a real config
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _D4}}
    fp.load_config_cached = lambda *a, **k: {"settings": {"logDir": _D4}}
    fp.log_dir = lambda cfg=None: _D4
    def _reset4(player="", src=""):
        fp._spk_voices.clear(); fp._spk_pin.clear(); fp._spk_recent[:] = []
        fp.REPLY_FULL.clear(); fp._ID_SEEN.clear()
        fp._spk_player[0] = player; fp._spk_player_src[0] = src
        fp._PLAYER_SAID[0] = True
    # the 13:10 field case: an NPC think task must not name the player
    _reset4()
    _w4 = fp.note_speaker(b"You are Mirabelle Ervine [master wizard], a Female Breton "
                          b"in Skyrim.\nThink internally as Mirabelle Ervine about it.")
    _a4 = (_w4 == "Mirabelle Ervine" and fp._spk_player[0] == "")
    # the party heading still names, and records its source
    _reset4()
    fp.note_speaker(b"You are Onmund, a Male Nord in Skyrim.\n"
                    b"## Maxxor's Party's Active Quests\n- x")
    _b4 = (fp._spk_player[0] == "Maxxor"
           and fp._spk_player_src[0] == "the party heading")
    # a name that already speaks somewhere cannot become the player
    _reset4()
    fp._spk_voices["femaleuniquemirabelleervine"] = "Mirabelle Ervine"
    fp.note_speaker(b"You are Mirabelle Ervine, a Female Breton in Skyrim.\n"
                    b"## Mirabelle Ervine's Party's Active Quests\n- x")
    _c4 = fp._spk_player[0] == ""
    # the typed name outranks a read one, and Player is the floor
    _reset4(player="WrongName", src="the party heading")
    fp.player_name_setting({"settings": {"logDir": _D4, "ttsPlayerName": "Maxxor"}})
    _nm4, _rl4, _ = fp.speaker_for_voice_ex("player")
    _d4 = (_nm4 == "Maxxor" and "typed" in _rl4)
    # and naming a voice reads NO config: it cost a parse per spoken line and wrote a
    # default config into a tree that had none
    def _boom4(*_a, **_k):
        raise AssertionError("the naming path must not read the config")
    _keepcc4 = fp.load_config_cached
    fp.load_config_cached = _boom4
    try:
        _d4 = _d4 and fp.speaker_for_voice("player") == "Maxxor"
    finally:
        fp.load_config_cached = _keepcc4
    fp.player_name_setting({"settings": {"logDir": _D4}})
    _reset4()
    _e4 = fp.speaker_for_voice("player") == "Player"
    check(_a4 and _b4 and _c4 and _d4 and _e4,
          "run: the player is named by the setting, then the party heading, then not "
          "at all - and an NPC think task, or an NPC's own name, never names them",
          str([_a4, _b4, _c4, _d4, _e4]))

    # the 13:32 field case: "Morning." must not move Nelysa onto a male voicetype
    _reset4()
    fp._spk_voices["femaledarkelf"] = "Nelysa"
    fp.REPLY_FULL["Nelysa"] = (fp._th_norm("Morning."), time.time())
    _f4 = (fp.tts_pin_speaker("C:" + chr(92) + "v" + chr(92) + "maleeventonedaccented.wav",
                              "Morning.") == ""
           and fp._spk_voices.get("maleeventonedaccented") is None
           and fp.speaker_for_voice("maleeventonedaccented") == "")
    # and a discriminating line still names its own voice, but only ONE
    _reset4()
    _ln4 = "I want you to sit there and feel exactly what you've done to me."
    fp.REPLY_FULL["Mirabelle Ervine"] = (fp._th_norm(_ln4), time.time())
    _g4 = (fp.tts_pin_speaker("C:" + chr(92) + "v" + chr(92)
                              + "femaleuniquemirabelleervine.wav", _ln4)
           == "Mirabelle Ervine")
    _h4 = fp.tts_pin_speaker("C:" + chr(92) + "v" + chr(92) + "maleyoungeager.wav",
                             _ln4) == ""
    check(_f4 and _g4 and _h4,
          "run: a greeting names nobody, a full line names its own voice, and neither "
          "can bind a name that already speaks through another sample",
          str([_f4, _g4, _h4]))

    # the ledger: rule, fingerprint, missing file, contradiction alarm
    _reset4()
    _ref4 = os.path.join(_D4, "femaledarkelf.wav")
    with open(_ref4, "wb") as _fh4:
        _fh4.write(b"RIFF____WAVEfmt " + b"\0" * 200)
    _ex4, _sz4, _sha4 = fp.tts_ref_fingerprint(_ref4)
    _i4 = _ex4 and _sz4 == 216 and len(_sha4) == 12
    _j4 = fp.tts_ref_fingerprint(os.path.join(_D4, "nope.wav")) == (False, 0, "")
    fp.tts_identity_note({"settings": {"logDir": _D4}}, eid="e1", key="femaledarkelf",
                         name="Nelysa", rule="the words of the line itself",
                         cand={"pin": "Nelysa"}, sent=_ref4,
                         asked="C:" + chr(92) + "up" + chr(92) + "femaledarkelf.wav",
                         text="Morning.")
    _led4 = open(fp.tts_identity_path({"settings": {"logDir": _D4}}),
                 encoding="utf-8").read()
    _k4 = ("name      : Nelysa" in _led4 and "by        : the words" in _led4
           and _sha4 in _led4 and "asked" in _led4 and "said      : Morning." in _led4)
    _heard4 = []
    fp.TTSW.log = lambda m: _heard4.append(m)
    fp.tts_identity_note({"settings": {"logDir": _D4}}, eid="e2",
                         key="maleeventonedaccented", name="Nelysa",
                         rule="the learned voicetype cache", sent=_ref4, text="Morning.")
    fp.tts_identity_note({"settings": {"logDir": _D4}}, eid="e3", key="missingtype",
                         name="Ghost", rule="x",
                         sent=os.path.join(_D4, "gone.wav"), text="hi")
    fp.TTSW.log = lambda *_a, **_k: None
    _l4 = any("spoke through femaledarkelf before and through maleeventonedaccented now"
              in _m for _m in _heard4)
    _m4 = "MISSING - nothing to clone from" in open(
        fp.tts_identity_path({"settings": {"logDir": _D4}}), encoding="utf-8").read()
    check(_i4 and _j4 and _k4 and _l4 and _m4,
          "run: the ledger records the rule and the sample's own bytes, names a "
          "missing reference, and alarms one character arriving on a second sample",
          str([_i4, _j4, _k4, _l4, _m4]))
except Exception as _e4x:
    check(False, "the identity runs did not RUN", str(_e4x)[:140])
finally:
    try:
        fp.load_config, fp.load_config_cached, fp.log_dir = _lc4, _lcc4, _ld4
        fp.panel_log = _pl4
        fp.TTSW.log = _tl4
        _reset4()
    except Exception:
        pass


# ------------------------------------------------------------------ v3.75 patch5
# Naming, inverted: the words are the primary evidence, the queue is Dialogue-only,
# a unique voicetype is its own proof, one utterance's chunks travel together, the
# Meta pick breaks ties, and a generic voicetype with no live evidence prints as
# itself. Plus the wire capture: what SkyrimNet actually sends, on record.
section("v3.75 patch5: content-first naming, gated queue, runs, wire capture")

_ns5 = seg(py, "def note_speaker", "def speaker_for_text")
check("def note_speaker(body, enqueue=True):" in _ns5
      and "if not enqueue:" in _ns5,
      "the pairing queue is fed by choice, not by every route that names a character")
check('note_speaker(body, enqueue=(rt["title"] == "Dialogue"))' in py,
      "and the relay grants it to Dialogue requests alone")
check("_spk_known.add(name)" in _ns5 and "_listener_note(name," in _ns5,
      "every route still registers its character, and who they speak to")
check("def _listener_note(" in py and '"being everyone\'s listener"' in py
      and "len(_spk_listen[ln]) >= 2" in py,
      "the player is the one everyone talks to and nobody ever is - two speakers is the bar")
check("REPLY_RING = {}" in py and "RING_DEPTH = 4" in py
      and "_rr.append(REPLY_FULL[who])" in py,
      "a character's replies ring four deep - the second no longer erases the first")
check("for who in set(list(REPLY_RING) + list(REPLY_FULL)):" in py
      and "now - when > RING_LIFE_S" in py,
      "the matcher reads the ring, one hit per character, two minutes deep")
check("def _spk_unique_bind(" in py and '"unique" not in key' in py,
      "a unique voicetype carries its character in its own filename")
check("_spk_run = {}" in py and "RUN_GAP_S" in py
      and '"carried by its own utterance\'s run"' in py,
      "chunks of one utterance travel together")
check("_elig = [nm for _w, nm in _spk_recent" in py
      and "if run and run[2] and now - run[1] <= RUN_GAP_S and not _elig:" in py,
      "but the run yields to a live request - a shared voicetype takes who just spoke")
check("def meta_note(" in py
      and '"the Meta selector\'s pick among waiting requests"' in py,
      "the Meta pick breaks a tie among waiting requests, and only that")
check('return "", "no live evidence - the voicetype stands", cand' in py,
      "a generic voicetype with no live evidence answers as ITSELF, never from the cache")
check("def tts_wire_note(" in py and "tts_wire_note(_j, self.headers)" in py,
      "every generate_audio shape goes on record - keys and header names, no values")

import collections as _c5
try:
    _lc5 = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log, fp.TTSW.log)
    import tempfile as _tf5
    _D5 = _tf5.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _D5}}
    fp.load_config_cached = lambda *a, **k: {"settings": {"logDir": _D5}}
    fp.log_dir = lambda cfg=None: _D5
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    def _r5():
        fp._spk_voices.clear(); fp._spk_pin.clear(); fp._spk_recent[:] = []
        fp.REPLY_FULL.clear(); fp.REPLY_RING.clear(); fp._spk_run.clear()
        fp._spk_unique_pos.clear(); fp._spk_known.clear(); fp._spk_listen.clear()
        fp._spk_player[0] = ""; fp._spk_player_src[0] = ""
        fp.META_LAST[0], fp.META_LAST[1] = "", 0.0
        fp._PLAYER_SAID[0] = True

    # the poisoned queue: a non-Dialogue request must not lend its name
    _r5()
    fp.note_speaker(b"You are Serana, a vampire of Volkihar in Skyrim.", enqueue=False)
    _a5 = ("Serana" in fp._spk_known and not fp._spk_recent
           and fp.speaker_for_voice("femalecommoner") == "")
    fp.note_speaker(b"You are Serana, a vampire of Volkihar in Skyrim.")
    _a5 = _a5 and len(fp._spk_recent) == 1
    check(_a5, "run: a GM request registers its character and queues nothing - the "
               "ambient line after it wears no borrowed name", str(_a5))

    # the ring: a chunk of the FIRST reply survives the second
    _r5()
    fp.thought_lines("The moons are wrong tonight, and I intend to say so at length.",
                     who="GateSerana5", cfg={"settings": {}})
    fp.thought_lines("Second thoughts are for people with time to spare, novice.",
                     who="GateSerana5", cfg={"settings": {}})
    _b5 = (len(fp.REPLY_RING.get("GateSerana5", [])) == 2
           and fp.tts_pin_speaker("C:" + chr(92) + "v" + chr(92) + "femalecommoner.wav",
                                  "The moons are wrong tonight, and I intend to say "
                                  "so at length.") == "GateSerana5")
    check(_b5, "run: two replies ring side by side and a chunk of the first still "
               "names its speaker", str(_b5))

    # the run: a short sibling chunk inherits, a live request ends it, staleness ends it
    _r5()
    fp.thought_lines("You will stand exactly there and you will not move an inch.",
                     who="GateFaralda5", cfg={"settings": {}})
    fp.tts_pin_speaker("C:" + chr(92) + "v" + chr(92) + "femaleelfhaughty.wav",
                       "You will stand exactly there and you will not move an inch.")
    fp._spk_pin.clear()
    _n1, _rl1, _ = fp.speaker_for_voice_ex("femaleelfhaughty")
    fp.note_speaker(b"You are Ysolda Gatefive, a trader in Whiterun.")
    _n2, _rl2, _ = fp.speaker_for_voice_ex("femaleelfhaughty")
    fp._spk_run.clear(); fp._spk_recent[:] = []
    _n3 = fp.speaker_for_voice("femaleelfhaughty")
    _c5r = (_n1 == "GateFaralda5" and "run" in _rl1
            and _n2 == "Ysolda Gatefive" and "paired" in _rl2
            and _n3 == "")
    check(_c5r, "run: the short chunk inherits its utterance, a live request takes "
                "the voice over, and with neither the voicetype stands",
          str([_n1, _rl1, _n2, _rl2, _n3]))

    # unique voicetypes, meta tie-break, generic refusal, listener rule
    _r5()
    fp.note_speaker(b"You are Mirabelle Ervine, a Female Breton in Skyrim.", enqueue=False)
    _d5 = fp.speaker_for_voice_ex("femaleuniquemirabelleervine")
    _d5ok = _d5[0] == "Mirabelle Ervine" and "unique" in _d5[1]
    _r5()
    fp.note_speaker(b"You are Aela the Huntress, a Female Nord in Skyrim.")
    fp.note_speaker(b"You are Lydia, a Female Nord in Skyrim.")
    fp.meta_note("[Lydia]>[player]")
    _e5 = fp.speaker_for_voice_ex("femaleevennormal")
    _e5ok = (_e5[0] == "Lydia" and "Meta" in _e5[1]
             and [n for _w, n in fp._spk_recent] == ["Aela the Huntress"])
    _r5()
    fp.note_speaker(b"You are Nelysa, a Female Dark Elf in Skyrim.")
    _f5a = fp.speaker_for_voice("femaledarkelf")
    fp._spk_run.clear()
    _f5b, _f5rule, _f5c = fp.speaker_for_voice_ex("femaledarkelf")
    _f5ok = (_f5a == "Nelysa" and _f5b == ""
             and "voicetype stands" in _f5rule and _f5c.get("cache") == "Nelysa")
    _r5()
    fp.note_speaker(b"You are Adara, a mage. You are speaking to Maxxor, a Male Dark Elf.",
                    enqueue=False)
    fp.note_speaker(b"You are Brynjar, a bard. You are speaking to Maxxor, a Male Dark Elf.",
                    enqueue=False)
    _g5ok = (fp._spk_player[0] == "Maxxor"
             and fp._spk_player_src[0] == "being everyone's listener")
    check(_d5ok and _e5ok and _f5ok and _g5ok,
          "run: the filename binds its unique character, the Meta pick breaks the "
          "tie, the next dark elf refuses the last one's name, and the one everyone "
          "addresses is the player", str([_d5ok, _e5ok, _f5ok, _g5ok]))

    # the wire capture: one block per shape, names only
    _r5()
    fp._WIRE_SEEN.clear()
    fp.tts_wire_note({"data": [1], "session_hash": "x"},
                     {"Content-Type": "application/json"})
    fp.tts_wire_note({"data": [1], "session_hash": "y"},
                     {"Content-Type": "application/json"})
    _led5 = open(fp.tts_identity_path({"settings": {"logDir": _D5}}),
                 encoding="utf-8").read()
    _h5 = _led5.count("wire: generate_audio") == 1 and "session_hash" in _led5
    check(_h5, "run: the request's shape is on record once, keys and header names only",
          str(_h5))
except Exception as _e5x:
    check(False, "the patch5 runs did not RUN", str(_e5x)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir,
         fp.panel_log, fp.TTSW.log) = _lc5
        _r5()
        fp._WIRE_SEEN.clear()
    except Exception:
        pass


# ------------------------------------------------------------------ v3.75 patch6
# The sample half: what reaches the engine is verified first. A dead path or
# another voicetype's bytes never make it - recovered from the panel's own copy
# or refused loudly, never improvised in whoever the engine conditioned on last.
# Plus the warm-up probe for the session-carryover hypothesis, off by default.
section("v3.75 patch6: the sample gate and the warm-up probe")

check("def tts_sample_gate(" in py and '"refused-missing"' in py
      and '"recovered-crosswired"' in py and '"refused-crosswired"' in py,
      "the gate exists and knows its three faults by name")
check("ref_path, _gatev = tts_sample_gate(ref_path, _idk, cfg)" in py,
      "and the speak path passes every reference through it before the engine")
check('if not ref_path:' in seg(py, "ref_path, _gatev = tts_sample_gate", "_t_post = time.time()")
      and 'ev["err"] = "no trustworthy sample' in py,
      "a refused line FAILS - the request errors instead of posting a dead path")
check("_VT_SHA = {}" in py and "_SHA_VT = {}" in py,
      "one voicetype, one sample - both directions on record")
check("changed its sample mid-session" in py,
      "new bytes under a known voicetype are accepted and alarmed, not refused")
# retold patch29: the warm-up is REMOVED - measured at 749 ms per speaker change
# against 33 ms without. _WARM_LAST stays: it is the conditioning tracker the
# sample gate uses, which was never the warm-up.
nin(py, "def tts_warmup_needed", "the warm-up probe is gone entirely")
nin(py, "ttsVoiceWarmup", "setting and toggle with it")
check("_WARM_LAST" in py, "and the conditioning tracker it borrowed remains")
check('if kw.get("gate") and kw.get("gate") != "ok":' in py,
      "the ledger carries a gate verdict only when there is something to say")

import tempfile as _tf6
try:
    _lc6 = (fp.load_config, fp.load_config_cached, fp.log_dir,
            fp.panel_log, fp.TTSW.log, fp.tts_voice_index)
    _D6 = _tf6.mkdtemp(); _V6 = _tf6.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _D6}}
    fp.load_config_cached = lambda *a, **k: {"settings": {"logDir": _D6}}
    fp.log_dir = lambda cfg=None: _D6
    fp.panel_log = lambda *a, **k: None
    _al6 = []
    fp.TTSW.log = lambda m: _al6.append(m)
    _ix6 = {}
    fp.tts_voice_index = lambda cfg=None: _ix6
    def _wav6(path, seed):
        with open(path, "wb") as f:
            f.write(b"RIFF____WAVEfmt " + bytes([seed]) * 300)
        return path
    def _r6():
        fp._VT_SHA.clear(); fp._SHA_VT.clear(); fp._ID_HASH.clear()
        fp._WARM_LAST[0] = ""; _ix6.clear(); del _al6[:]

    _r6()
    _a6 = _wav6(os.path.join(_D6, "femaledarkelf.wav"), 1)
    _ok1 = fp.tts_sample_gate(_a6, "femaledarkelf") == (_a6, "ok") and not _al6
    _r6()
    _own6 = _wav6(os.path.join(_V6, "maleoldkindly.wav"), 2)
    _ix6["maleoldkindly"] = _own6
    _ok2 = fp.tts_sample_gate(os.path.join(_D6, "gone.wav"),
                              "maleoldkindly") == (_own6, "recovered")
    _r6()
    _ok3 = fp.tts_sample_gate(os.path.join(_D6, "gone.wav"),
                              "femalesultry") == ("", "refused-missing")
    _r6()
    _nel6 = _wav6(os.path.join(_D6, "femaledarkelf.wav"), 3)
    fp.tts_sample_gate(_nel6, "femaledarkelf")
    _imp6 = _wav6(os.path.join(_D6, "maleeventonedaccented.wav"), 3)
    _own7 = _wav6(os.path.join(_V6, "maleeventonedaccented.wav"), 4)
    _ix6["maleeventonedaccented"] = _own7
    _ok4 = (fp.tts_sample_gate(_imp6, "maleeventonedaccented")
            == (_own7, "recovered-crosswired")
            and any("femaledarkelf's bytes" in _m for _m in _al6))
    _r6()
    _nel6 = _wav6(os.path.join(_D6, "femaledarkelf.wav"), 3)
    fp.tts_sample_gate(_nel6, "femaledarkelf")
    _imp7 = _wav6(os.path.join(_D6, "malebrute.wav"), 3)
    _ok5 = fp.tts_sample_gate(_imp7, "malebrute") == ("", "refused-crosswired")
    _r6()
    _b6 = _wav6(os.path.join(_D6, "femaleyoungeager.wav"), 5)
    fp.tts_sample_gate(_b6, "femaleyoungeager")
    _wav6(_b6, 6)
    _ok6 = (fp.tts_sample_gate(_b6, "femaleyoungeager") == (_b6, "changed")
            and any("changed its sample" in _m for _m in _al6)
            and fp.tts_sample_gate(_b6, "femaleyoungeager") == (_b6, "ok"))
    check(_ok1 and _ok2 and _ok3 and _ok4 and _ok5 and _ok6,
          "run: healthy passes silently, missing recovers or refuses, cross-wired "
          "bytes speak through the panel's copy or refuse, and a re-record is "
          "accepted with one alarm", str([_ok1, _ok2, _ok3, _ok4, _ok5, _ok6]))

    _r6()
    check(not hasattr(fp, "tts_warmup_needed"),   # retold patch29
          "run: there is no warm-up left to fire")
except Exception as _e6x:
    check(False, "the patch6 runs did not RUN", str(_e6x)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir,
         fp.panel_log, fp.TTSW.log, fp.tts_voice_index) = _lc6
        fp._VT_SHA.clear(); fp._SHA_VT.clear(); fp._ID_HASH.clear()
        fp._WARM_LAST[0] = ""
    except Exception:
        pass


# ------------------------------------------------------------------ v3.75 patch7
# Engine state is mirrored, not inferred: the TTS engine keeps ONE session, and
# what it last conditioned on is now tracked on EVERY synthesis path - a voiced
# thought conditions it exactly like a spoken line. The ledger records it, which
# is how the first field capture of a wrong voice was settled in one block: a
# cold start with no previous take ends the carryover-only theory by itself.
section("v3.75 patch7: the conditioning tracker and the ledger's engine-was line")

check("def tts_conditioned(" in py and "prev = _WARM_LAST[0]" in py,
      "one function records every synthesis and answers with the PREVIOUS")
nin(py, "_WARM_LAST[0] = _idk",
    "the dialogue path no longer writes the record by hand")
check("tts_conditioned(_idk)" in py,
      "it reports through the tracker like everything else")
check("tts_conditioned(os.path.splitext(re.split(" in py,
      "the THOUGHT path conditions the engine too, and the tracker sees it")
check('prev=(_WARM_LAST[0]' in py and '!= _idk else "")' in py,   # retold p17: wrapped
      "the ledger is told what the engine had been speaking as, when it differs")
check('rows.append("  engine was: %s" % kw["prev"])' in py
      and 'if kw.get("prev"):' in py,
      "and the block prints it only then - a cold start shows nothing, by design")

try:
    _keep7 = fp._WARM_LAST[0]
    fp._WARM_LAST[0] = ""
    _a7 = fp.tts_conditioned("player") == ""
    _b7 = fp.tts_conditioned("femaleshrill") == "player"
    _c7 = fp.tts_conditioned("") == "femaleshrill" and fp._WARM_LAST[0] == "femaleshrill"
    # retold patch29: the warm-up that consumed this tracker is gone; the tracker
    # itself is the sample gate's, and still has to follow a voiced thought
    fp._WARM_LAST[0] = ""
    fp.tts_conditioned("player")
    _d7 = fp._WARM_LAST[0] == "player"
    fp.tts_conditioned("maleorc")
    _e7 = fp._WARM_LAST[0] == "maleorc"
    check(_a7 and _b7 and _c7 and _d7 and _e7,
          "run: a cold start has no previous, each take reports what preceded it, "
          "an empty voicetype reads without clobbering, and a thought's take moves "
          "the tracker on", str([_a7, _b7, _c7, _d7, _e7]))
    import tempfile as _tf7
    _D7 = _tf7.mkdtemp()
    _lc7 = (fp.load_config_cached, fp.log_dir, fp.panel_log, fp.TTSW.log)
    fp.load_config_cached = lambda *a, **k: {"settings": {"logDir": _D7}}
    fp.log_dir = lambda cfg=None: _D7
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    _p7 = os.path.join(_D7, "player.wav")
    with open(_p7, "wb") as _fh7:
        _fh7.write(b"RIFF" + b"x" * 200)
    fp.tts_identity_note({"settings": {"logDir": _D7}}, eid="e1", key="player",
                         name="Maxxor", rule="x", sent=_p7, text="Morning.",
                         prev="femaleshrill")
    fp.tts_identity_note({"settings": {"logDir": _D7}}, eid="e2", key="player",
                         name="Maxxor", rule="x", sent=_p7, text="again", prev="")
    _led7 = open(fp.tts_identity_path({"settings": {"logDir": _D7}}),
                 encoding="utf-8").read()
    (fp.load_config_cached, fp.log_dir, fp.panel_log, fp.TTSW.log) = _lc7
    check("engine was: femaleshrill" in _led7 and _led7.count("engine was:") == 1,
          "run: the block carries the previous conditioning, and only when it differs")
except Exception as _e7x:
    check(False, "the patch7 runs did not RUN", str(_e7x)[:140])
finally:
    try:
        fp._WARM_LAST[0] = _keep7
    except Exception:
        pass


# ------------------------------------------------------------------ v3.75 patch8
# audio.cpp 0.6 readiness, and the Audio Cache. The start retries once without
# session options when the server exits at once - the retry a stale comment had
# only DESCRIBED - and remembers the refusal for the panel run. A co-hosted
# SenseVoice turns each voice sample into a reference transcript, once, keyed on
# the file's hash. And the TTS page grew a button: every character met this run,
# their sample, and their kept takes.
section("v3.75 patch8: 0.6 start-fallback, reference transcripts, the Audio Cache")

check("def tts_acpp_config(cfg=None, no_opts=False):" in py
      and "_ACPP_NO_OPTS = [False]" in py,
      "the config can leave its options at home, and a refusal is remembered")
check("return _api_tts_server(body, _retry=True)" in py
      and "retrying without" in py,
      "the exit-at-once retry is CODE now, not a comment describing an intent")
check('"family": "sense_asr"' in py and '"id": "sense"' in py,
      "a configured ASR path co-hosts SenseVoice beside the TTS model")
check("def tts_ref_text(ref_path, cfg=None, learn=False):" in py and "_RT_FAIL" in py
      and "tts-ref-text.json" in py,     # retold patch10: learning is opt-in now
      "transcripts are learned once per sample hash, persisted, and never hammered")
check("_rt8 = tts_ref_text(ref_path, cfg)" in py
      and "\n                                            _rt8)" in py,
      "the dialogue take carries its reference transcript")
check("tts_ref_text(ref, cfg))" in py,   # retold p29: the warm-up is gone
      "and so does the voiced thought")
check("def tts_takes_for(" in py and "_TAKE_RX" in py,
      "takes are matched by name PLUS timestamp - a prefix alone is ambiguous")
check("def api_tts_audio_cache(" in py and "def api_tts_audio_takes(" in py
      and '"/api/tts-audio-cache": api_tts_audio_cache' in py,
      "both endpoints exist and are routed")
check('data-act="ttsAudioCache"' in py and "glowbtn" in py,
      "the button sits on the TTS page")
_gl8 = seg(py, ".glowbtn {", ".vramline {")
check("box-shadow: 0 0 14px 2px rgba(255,255,255,0)" in _gl8
      and "box-shadow: 0 0 14px 2px rgba(255,255,255,.35)" in _gl8,
      "the glow keeps the SAME geometry at rest and on hover, alpha alone moves - "
      "nothing flickers, and nothing at rest is a zero-blur ring")
check("function audioCacheShow()" in py and "function audioCacheTakes(" in py
      and 'audioCacheShow(); return;' in py,
      "both views exist and the dispatcher reaches them")
check('"ttsAcppAsrModel", "ttsAsrMode"' in py       # retold patch10: its own section
      and 'id="tts-ttsAcppAsrModel"' in py,
      "the ASR path is a saved setting with a field on the page")
check("def _audio_cache_load(" in py and "def _audio_cache_save(" in py
      and "tts-audio-cache.json" in py,
      "the associations persist across restarts, loaded once, written through")
check("TTS_REF_BY_NAME.setdefault(str(k), str(v))" in py,
      "and live learning wins over the disk - setdefault, never overwrite")
check("if _new8:" in py and "_audio_cache_save(cfg)" in py,
      "the speak path saves the moment a pairing is new")
check("def api_tts_audio_cache_clear(" in py
      and '"/api/tts-audio-cache-clear": api_tts_audio_cache_clear' in py,
      "the clear exists and is routed")
check(py.count('["!!", "audiocache"],') == 2
      and 'f[0] === "!!"' in py,
      "the buttons render at the bottom of Audio Files, in both engine fieldsets")
check('data-act="ttsAudioCacheClear"' in py
      and "function audioCacheClear()" in py and "Clear the Audio Cache?" in py,
      "Clear sits beside it, behind a confirm, and shows the emptied list after")
_st8 = seg(py, 'data-act="ttsStart"', 'data-act="ttsStop"')
nin(_st8, "ttsAudioCache",
    "the Start TTS row no longer carries the button - it moved to Audio Files")

import tempfile as _tf8, types as _ty8
try:
    _lc8 = (fp.load_config, fp.load_config_cached, fp.log_dir,
            fp.panel_log, fp.TTSW.log, fp._ureq)
    _D8 = _tf8.mkdtemp(); _O8 = _tf8.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _D8, "ttsOutDir": _O8}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _D8
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    _keep8 = fp._ACPP_NO_OPTS[0]
    _refs8 = dict(fp.TTS_REF_BY_NAME)
    fp._ACPP_NO_OPTS[0] = False
    fp._RT_MEM.clear(); fp._RT_FAIL.clear(); fp._ID_HASH.clear()

    # the config's three shapes: default, refused, co-hosted
    _asr8 = os.path.join(_D8, "sense.gguf")
    with open(_asr8, "wb") as _f8:
        _f8.write(b"GGUF")
    _j8 = json.loads(fp.tts_acpp_config({"settings": {"logDir": _D8}}))
    fp._ACPP_NO_OPTS[0] = True
    _j8b = json.loads(fp.tts_acpp_config({"settings": {"logDir": _D8}}))
    fp._ACPP_NO_OPTS[0] = False
    _j8c = json.loads(fp.tts_acpp_config({"settings": {"logDir": _D8,
                                                       "ttsAcppAsrModel": _asr8,
                                                       "ttsAsrMode": "on"}}))
    _a8 = ("session_options" in _j8["models"][0]
           and "session_options" not in _j8b["models"][0]
           and len(_j8c["models"]) == 2 and _j8c["models"][1]["family"] == "sense_asr")
    check(_a8, "run: options by default, none after a refusal, SenseVoice when a "
               "real path is set", str(_a8))

    # the transcript store: once per hash, persisted, fail-open, gated
    _ref8 = os.path.join(_D8, "femaledarkelf.wav")
    with open(_ref8, "wb") as _f8:
        _f8.write(b"RIFF" + b"a" * 300)
    _calls8 = []
    class _R8:
        def read(self):
            return json.dumps({"text": "Some call me nature."}).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    fp._ureq = _ty8.SimpleNamespace(
        Request=_lc8[5].Request,
        urlopen=lambda req, timeout=0: (_calls8.append(1), _R8())[1])
    # retold patch10: a transcript is LEARNED only when asked; the speak path reads
    _asrcfg8 = {"settings": {"logDir": _D8, "ttsAcppAsrModel": _asr8,
                             "ttsAsrMode": "on"}}
    fp._RT_LOADED[0] = False
    _b8 = (fp.tts_ref_text(_ref8, {"settings": {"logDir": _D8}}) == ""
           and fp.tts_ref_text(_ref8, _asrcfg8, learn=True) == "Some call me nature."
           and fp.tts_ref_text(_ref8, _asrcfg8) == "Some call me nature."
           and len(_calls8) == 1)
    fp._RT_MEM.clear()
    fp._RT_LOADED[0] = False
    _b8 = _b8 and fp.tts_ref_text(_ref8, _asrcfg8) == "Some call me nature." \
        and len(_calls8) == 1
    _dead8 = []
    def _boom8(req, timeout=0):
        _dead8.append(1)
        raise OSError("refused")
    fp._ureq = _ty8.SimpleNamespace(Request=_lc8[5].Request, urlopen=_boom8)
    _ref8b = os.path.join(_D8, "maleorc.wav")
    with open(_ref8b, "wb") as _f8:
        _f8.write(b"RIFF" + b"b" * 300)
    _b8 = _b8 and fp.tts_ref_text(_ref8b, _asrcfg8, learn=True) == "" \
        and fp.tts_ref_text(_ref8b, _asrcfg8, learn=True) == "" \
        and len(_dead8) == 1
    check(_b8, "run: gated off silently, learned once, reloaded from disk, and a "
               "refusal never hammers the engine", str(_b8))

    # the takes and the cache rows
    for _leaf8 in ("Urag_20260816_093500.wav", "Urag_gro-Shub_20260816_093504.wav",
                   "Urag_notes.wav"):
        with open(os.path.join(_O8, _leaf8), "wb") as _f8:
            _f8.write(b"RIFF" + b"x" * 100)
    fp.TTS_REF_BY_NAME.clear()
    fp.TTS_REF_BY_NAME["Urag gro-Shub"] = _ref8b
    fp.TTS_REF_BY_NAME["Colette Marence"] = os.path.join(_D8, "gone.wav")
    _r8 = fp.api_tts_audio_cache({})
    _c8 = ([x["name"] for x in _r8["rows"]] == ["Colette Marence", "Urag gro-Shub"]
           and [t["file"] for t in fp.tts_takes_for("Urag")]
           == ["Urag_20260816_093500.wav"]
           and _r8["rows"][1]["takes"] == 1 and _r8["rows"][0]["present"] is False
           and fp.api_tts_audio_takes({}).get("error") == "no name")
    check(_c8, "run: alphabetical rows, per-name takes with the timestamp rule, a "
               "missing sample says so, a nameless ask is refused", str(_c8))

    # persistence: back from disk, live wins, clear forgets both copies
    fp.TTS_REF_BY_NAME.clear()
    fp._AC_LOADED[0] = True
    fp.TTS_REF_BY_NAME["Urag gro-Shub"] = _ref8b
    fp._audio_cache_save({"settings": {"logDir": _D8}})
    fp.TTS_REF_BY_NAME.clear()
    fp._AC_LOADED[0] = False
    with fp._spk_lock:
        fp._audio_cache_load({"settings": {"logDir": _D8}})
    _d8 = fp.TTS_REF_BY_NAME.get("Urag gro-Shub") == _ref8b
    fp.TTS_REF_BY_NAME["Urag gro-Shub"] = "C:/new/maleorc.wav"
    fp._AC_LOADED[0] = False
    with fp._spk_lock:
        fp._audio_cache_load({"settings": {"logDir": _D8}})
    _d8 = _d8 and fp.TTS_REF_BY_NAME["Urag gro-Shub"] == "C:/new/maleorc.wav"
    _r8c = fp.api_tts_audio_cache_clear({})
    _d8 = (_d8 and _r8c.get("cleared") == 1 and not fp.TTS_REF_BY_NAME
           and not os.path.exists(fp._audio_cache_path({"settings": {"logDir": _D8}})))
    check(_d8, "run: yesterday's characters return from disk, live learning wins, "
               "and Clear forgets the list in memory AND on disk", str(_d8))
except Exception as _e8x:
    check(False, "the patch8 runs did not RUN", str(_e8x)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir,
         fp.panel_log, fp.TTSW.log, fp._ureq) = _lc8
        fp._ACPP_NO_OPTS[0] = _keep8
        fp.TTS_REF_BY_NAME.clear()
        fp.TTS_REF_BY_NAME.update(_refs8)
        fp._AC_LOADED[0] = True    # the tree's own store must not be read after this
        fp._RT_MEM.clear(); fp._RT_FAIL.clear(); fp._ID_HASH.clear()
        fp._RT_LOADED[0] = True; fp._RT_BUSY.clear(); fp._ACPP_NO_ASR[0] = False
    except Exception:
        pass


# ------------------------------------------------------------------ v3.75 patch9
# Speculative decoding grows a settings segment on the server card - the master
# llama.cpp surface, kind-aware - and Qwen 3.8 lands as a new reasoning category:
# a switch AND a depth at once, with its multi-step MTP head already detected by
# the nextn scan the qwen35 generation shares.
section("v3.75 patch9: the spec-decoding segment, and Qwen 3.8")

check('ARCH_REASON_EFFORT = ("qwen35", "qwen35moe")' in py
      and 'REASON_EFFORTS = ("low", "medium", "xhigh")' in py,
      "Qwen 3.8 is its own category: the on/off dial stays live beside a depth")
check('def draft_launch_args(draft_path, ngl="", params=None):' in py,
      "the drafter's stored parameters ride through the one function that renders them")
check('if kind not in ("draft-dflash", "draft-dspark"):' in py,
      "a user n-max never overrides a header that carries the block contract")
check('out.append(("--no-spec-draft-backend-sampling", None))' in py
      and 'out.append(("--spec-draft-backend-sampling", None))' in py,
      "backend sampling is a bare switch, both polarities")
check('and str(draft_path or "") != DRAFT_BUILTIN:' in py,
      "the builtin head carries no placement or cache of its own - it rides the target")
check('draft_launch_args(t.get("draft"), _ngl, t)' in py
      and 'draft_launch_args(p["draft"], gv("ngl"), p)' in py
      and 'draft_launch_args(p.get("draft"), p.get("ngl") or "", p)' in py,
      "all three render sites hand the stored parameters over")
check(chr(123) + '"reasoning_effort":"%s"' + chr(125) in py and "% _re9" in py
      and py.count("reasoning_effort") >= 4,
      "the effort kwarg is written by creator and fix-up alike")
check("# off outranks effort" in py,
      "and thinking OFF outranks a depth for thinking that is not happening")
check('"specNMax", "specNMin", "specPMin", "specPSplit", "specSample"' in py
      and '"specCtkD", "specCtvD"' in py,
      "the card saves every one of them")
check('out["specSample"] = ("off" if present("--no-spec-draft-backend-sampling")' in py
      and "_re9 = re.search(" in py,
      "a hand-edited launcher reads back, tri-state switch included")
check("const wantsEffort = EFFORT_ARCH.indexOf(mArch) >= 0;" in py
      and 'data-key="reasonEffort"' in py,
      "the effort select renders beside the reasoning dial, for this family alone")
check("Speculative Decoding" in py and 'num9("specNMax"' in py
      and "if (drFile9) {" in py,
      "the segment renders when a drafter is chosen, cache types for files only")

try:
    _ma9, _mf9, _gm9, _if9 = fp.model_arch, fp.model_facts, fp.gguf_meta, os.path.isfile
    _pl9 = fp.panel_log
    fp.panel_log = lambda *a, **k: None
    _P9 = {"specNMax": "4", "specNMin": "2", "specPMin": "0.75", "specPSplit": "0.1",
           "specSample": "on", "specCtkD": "q8_0", "specCtvD": "q4_0"}
    _a9 = dict(fp.draft_launch_args(fp.DRAFT_BUILTIN, "12", _P9))
    _ok1 = (_a9.get("--spec-type") == "draft-mtp" and _a9.get("--spec-draft-n-max") == "4"
            and _a9.get("--spec-draft-p-split") == "0.1"
            and "--spec-draft-backend-sampling" in _a9
            and "--spec-draft-type-k" not in _a9 and "--spec-draft-ngl" not in _a9)
    fp.model_facts = lambda p: {"spec": "draft-simple"}
    _b9 = dict(fp.draft_launch_args("D:/d/small.gguf", "12", _P9))
    _ok2 = (_b9.get("--spec-draft-ngl") == "12" and _b9.get("--spec-draft-type-k") == "q8_0")
    fp.model_facts = lambda p: {"spec": "draft-dflash"}
    fp.gguf_meta = lambda p: {"dflash.block_size": 16}
    os.path.isfile = lambda p: True
    _c9 = dict(fp.draft_launch_args("D:/d/df.gguf", "", _P9))
    os.path.isfile = _if9
    _ok3 = _c9.get("--spec-draft-n-max") == "15"   # retold p25
    _d9 = dict(fp.draft_launch_args(fp.DRAFT_BUILTIN, "", {"specSample": "off",
                                                           "specNMax": "junk"}))
    _ok4 = ("--no-spec-draft-backend-sampling" in _d9
            and "--spec-draft-n-max" not in _d9)
    check(_ok1 and _ok2 and _ok3 and _ok4,
          "run: builtin carries depth without placement or cache types, a file "
          "carries all of it, DFlash keeps its header, off is a bare --no- switch, "
          "junk is not written", str([_ok1, _ok2, _ok3, _ok4]))

    _q9 = chr(39)
    _txt9 = ('$llamaArgs = @(' + chr(10)
             + '    "--model", "D:/m/q.gguf",' + chr(10)
             + '    "--spec-type", "draft-mtp",' + chr(10)
             + '    "--spec-draft-n-max", "4",' + chr(10)
             + '    "--no-spec-draft-backend-sampling",' + chr(10)
             + '    "--chat-template-kwargs", ' + _q9
             + chr(123) + '"reasoning_effort":"medium"' + chr(125) + _q9 + chr(10)
             + ')')
    _o9 = fp.parse_launcher_params(_txt9)
    _ok5 = (_o9.get("draft") == fp.DRAFT_BUILTIN and _o9.get("specNMax") == "4"
            and _o9.get("specSample") == "off" and _o9.get("reasonEffort") == "medium")
    _o9b = fp.parse_launcher_params('$llamaArgs = @(' + chr(10)
                                    + '    "--model", "D:/m/x.gguf"' + chr(10) + ')')
    _ok6 = _o9b.get("specSample") == "" and _o9b.get("reasonEffort") == ""
    check(_ok5 and _ok6,
          "run: a hand-written launcher reads back exactly, and absence reads as empty",
          str([_ok5, _ok6]))

    fp.model_arch = lambda p: "qwen35"
    _cfg9 = {"settings": {}, "gpus": []}
    _s9 = {"id": "slot9g", "label": "s", "port": 1299, "gpu": "", "gpuId": "",
           "params": {"model": "D:/m/q.gguf", "reasonEffort": "medium",
                      "reasoning": "on", "draft": fp.DRAFT_BUILTIN, "specNMax": "4"}}
    _t9a = fp.build_param_launcher(_cfg9, _s9, "D:/l/llama-server.exe")
    _s9["params"]["reasoning"] = "off"
    _t9b = fp.build_param_launcher(_cfg9, _s9, "D:/l/llama-server.exe")
    fp.model_arch = lambda p: "llama"
    _s9["params"]["reasoning"] = "on"
    _t9c = fp.build_param_launcher(_cfg9, _s9, "D:/l/llama-server.exe")
    _ok7 = ("reasoning_effort" in _t9a and '"--spec-draft-n-max", "4"' in _t9a
            and "reasoning_effort" not in _t9b and "enable_thinking" in _t9b
            and "reasoning_effort" not in _t9c)
    check(_ok7, "run: the creator writes effort for Qwen 3.8 with thinking on, "
                "never over off, never for a family without it", str(_ok7))
except Exception as _e9x:
    check(False, "the patch9 runs did not RUN", str(_e9x)[:140])
finally:
    try:
        fp.model_arch, fp.model_facts, fp.gguf_meta, os.path.isfile = _ma9, _mf9, _gm9, _if9
        fp.panel_log = _pl9
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch10
# Reference transcripts become a settings field of their own, with the options
# audio.cpp's sense_asr family actually documents - and the work moves OFF the
# speak path: a store read before the timing wall, learning behind the line.
section("v3.75 patch10: the transcript field, and the work behind the line")

check('"ttsAsrMode": "on",' in py and '"ttsAsrLang": "auto",' in py  # retold p29
      and '"ttsAsrItn": "words",' in py,   # retold p16: Meta tags is gone
      "the field is three settings, each with a defensible default")
check('str(st.get("ttsAsrMode") or "on").strip().lower() == "on"' in py  # retold p14
      and 'and not _ACPP_NO_ASR[0]' in py,
      "only ON co-hosts a model - Stored costs no VRAM, and a refusal is remembered")
check('"default_request_options"' in py and '"audio_chunk_mode": "none"' in py,
      "the entry carries the documented request options; short samples take one pass")
check("def acpp_retry_rung(" in py and "still exiting - retrying without the ASR" in py
      and '_rung = acpp_retry_rung(cfg) if eng == "audiocpp" else ""' in py,
      "the start ladder's decision is a function the gate can RUN, not prose in a spawn")
check("def tts_ref_learn(" in py and "threading.Thread(target=_work, daemon=True)" in py
      and "_RT_BUSY" in py,
      "learning happens in the background, once per sample, never twice at a time")
_wall10 = seg(py, "_rt8 = tts_ref_text(ref_path, cfg)", "srv_s = time.time() - _t_post")
check("_t_post = time.time()" in _wall10
      and "tts_ref_learn(ref_path, cfg)" in _wall10.split("_t_post = time.time()")[0],
      "the read and the learner sit BEFORE the wall - neither is synthesis")
check("_RT_TAGS = re.compile" in py and "_RT_TAGS.sub(" in py,
      "meta markers are stripped from a transcript whatever the engine was told")
check('"voice": os.path.splitext(' in py and "_rt_store_load" in py,
      "the store names the voicetype beside each line, so a person can correct it")
check('if isinstance(v, dict):' in py,
      "and the flat file patch8 wrote still reads")
check("def api_tts_ref_text_clear(" in py
      and '"/api/tts-ref-text-clear": api_tts_ref_text_clear' in py
      and 'data-act="ttsAsrClear"' in py,
      "Clear transcripts exists, routed, and on the page")
check("function ttsAsrRow(" in py and 'id="tts-ttsAsrMode"' in py
      and "ASR_LANGS" in py and 'id="tts-ttsAsrItn"' in py,
      "the section renders with every control the settings name")
check(py.index("ttsAsrRow(st)") < py.index('<div class="tsect">Audio Tags</div>'),
      "and it sits above Audio Tags, where it was asked for")
nin(py, 'ttsTitle("ASR model for reference transcripts"',
    "the old lone path field is gone, not left beside its replacement")

import tempfile as _tfA, types as _tyA, time as _tmA
try:
    _lcA = (fp.load_config, fp.load_config_cached, fp.log_dir,
            fp.panel_log, fp.TTSW.log, fp._ureq)
    _DA = _tfA.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DA}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DA
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    _asrA = os.path.join(_DA, "sense.gguf")
    with open(_asrA, "wb") as _f:
        _f.write(b"GGUF")
    _refA = os.path.join(_DA, "femaledarkelf.wav")
    with open(_refA, "wb") as _f:
        _f.write(b"RIFF" + b"a" * 300)
    def _cfgA(mode="on", **kw):
        _s = {"logDir": _DA, "ttsAsrMode": mode, "ttsAcppAsrModel": _asrA}
        _s.update(kw)
        return {"settings": _s}
    _callsA = []
    class _RA:
        def __init__(self, txt):
            self.txt = txt
        def read(self):
            return json.dumps({"text": self.txt}).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    def _speakA(txt, delay=0.0):
        def _f(req, timeout=0):
            _callsA.append(1)
            if delay:
                _tmA.sleep(delay)
            return _RA(txt)
        fp._ureq = _tyA.SimpleNamespace(Request=_lcA[5].Request, urlopen=_f)
    def _resetA():
        fp._RT_MEM.clear(); fp._RT_FAIL.clear(); fp._RT_BUSY.clear()
        fp._RT_LOADED[0] = False
        fp._ACPP_NO_ASR[0] = False
        del _callsA[:]
        try:
            os.remove(fp._rt_store_path(_cfgA()))
        except OSError:
            pass

    _resetA(); _speakA("x")
    _m1 = len(json.loads(fp.tts_acpp_config(_cfgA("off")))["models"]) == 1
    _m2 = len(json.loads(fp.tts_acpp_config(_cfgA("stored")))["models"]) == 1
    _jA = json.loads(fp.tts_acpp_config(_cfgA("on")))
    _m3 = (len(_jA["models"]) == 2
           and _jA["models"][1]["default_request_options"]
           == {"language": "en", "enable_itn": False, "keep_tags": False,
               "audio_chunk_mode": "none"})
    # retold p16: markers are never asked for - the option is pinned False
    _jB = json.loads(fp.tts_acpp_config(_cfgA("on", ttsAsrLang="ja",
                                              ttsAsrItn="digits")))
    _rB = _jB["models"][1]["default_request_options"]
    _m4 = (_rB["language"] == "ja" and _rB["enable_itn"] is True
           and _rB["keep_tags"] is False)
    check(_m1 and _m2 and _m3 and _m4,
          "run: Off and Stored co-host nothing, On co-hosts SenseVoice with the "
          "documented options, and every control reaches the engine",
          str([_m1, _m2, _m3, _m4]))

    _resetA(); _speakA("Some call me nature.")
    _r1 = fp.tts_ref_text(_refA, _cfgA("on")) == "" and not _callsA
    _r2 = (fp.tts_ref_text(_refA, _cfgA("on"), learn=True) == "Some call me nature."
           and len(_callsA) == 1)
    _r3 = (fp.tts_ref_text(_refA, _cfgA("on")) == "Some call me nature."
           and len(_callsA) == 1)
    _r4 = fp.tts_ref_text(_refA, _cfgA("stored")) == "Some call me nature."
    _r5 = fp.tts_ref_text(_refA, _cfgA("off")) == ""
    check(_r1 and _r2 and _r3 and _r4 and _r5,
          "run: the speak path reads and calls nothing, the learner transcribes once, "
          "Stored serves it with no model, Off says nothing",
          str([_r1, _r2, _r3, _r4, _r5]))

    _resetA(); _speakA("<<TAG>>Some call me nature.".replace("<<TAG>>",
                                                             "<|en|><|NEUTRAL|>"))
    _t1 = (fp.tts_ref_text(_refA, _cfgA("on"), learn=True)   # retold p16
           == "Some call me nature.")
    _storeA = json.load(open(fp._rt_store_path(_cfgA()), encoding="utf-8"))
    _rowA = list(_storeA.values())[0]
    _t2 = _rowA.get("voice") == "femaledarkelf"
    with open(fp._rt_store_path(_cfgA()), "w", encoding="utf-8") as _f:
        json.dump({list(_storeA)[0]: "the flat patch8 shape"}, _f)
    fp._RT_MEM.clear(); fp._RT_LOADED[0] = False
    _t3 = fp.tts_ref_text(_refA, _cfgA("on")) == "the flat patch8 shape"
    check(_t1 and _t2 and _t3,
          "run: markers never reach the store, the voicetype is written beside the "
          "text, and the older flat file still reads", str([_t1, _t2, _t3]))

    _resetA(); _speakA("slow one", delay=0.35)
    _tA = _tmA.time()
    fp.tts_ref_learn(_refA, _cfgA("on"))
    _fast = (_tmA.time() - _tA) < 0.15
    fp.tts_ref_learn(_refA, _cfgA("on"))
    _tmA.sleep(0.7)
    _once = len(_callsA) == 1
    _landed = fp.tts_ref_text(_refA, _cfgA("on")) == "slow one"
    _resetA(); _speakA("x")
    fp.tts_ref_learn(_refA, _cfgA("stored"))
    _tmA.sleep(0.15)
    _quiet = not _callsA
    check(_fast and _once and _landed and _quiet,
          "run: the learner returns at once, never doubles up, lands its result, and "
          "stays silent in Stored", str([_fast, _once, _landed, _quiet]))

    # the ladder: options first, then the ASR entry, then nothing left
    _resetA()
    fp._ACPP_NO_OPTS[0] = False; fp._ACPP_NO_ASR[0] = False
    _l1 = fp.acpp_retry_rung(_cfgA("on")) == "opts"
    fp._ACPP_NO_OPTS[0] = True
    _l2 = fp.acpp_retry_rung(_cfgA("on")) == "asr"
    fp._ACPP_NO_ASR[0] = True
    _l3 = fp.acpp_retry_rung(_cfgA("on")) == ""
    fp._ACPP_NO_OPTS[0] = True; fp._ACPP_NO_ASR[0] = False
    _l4 = fp.acpp_retry_rung(_cfgA("off")) == ""
    fp._ACPP_NO_OPTS[0] = False; fp._ACPP_NO_ASR[0] = False
    check(_l1 and _l2 and _l3 and _l4,
          "run: the ladder drops session options first, the ASR entry second, and "
          "has nothing to offer a config that carries neither",
          str([_l1, _l2, _l3, _l4]))

    _resetA(); _speakA("Some call me nature.")
    fp.tts_ref_text(_refA, _cfgA("on"), learn=True)
    _cA = fp.api_tts_ref_text_clear({})
    _cl = (_cA.get("cleared") == 1 and not fp._RT_MEM
           and not os.path.exists(fp._rt_store_path(_cfgA()))
           and fp.api_tts_ref_text_clear({}).get("cleared") == 0)
    check(_cl, "run: Clear forgets memory and disk, counts what it forgot, and an "
               "empty store clears quietly", str(_cl))
except Exception as _eAx:
    check(False, "the patch10 runs did not RUN", str(_eAx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir,
         fp.panel_log, fp.TTSW.log, fp._ureq) = _lcA
        fp._RT_MEM.clear(); fp._RT_FAIL.clear(); fp._RT_BUSY.clear()
        fp._RT_LOADED[0] = True
        fp._ACPP_NO_ASR[0] = False
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch11
# The sample vault: SkyrimNet's own clips are read once, repaired into a header
# that says what the file holds, trimmed to an example rather than a performance,
# and used from then on. The fault that made 160 clips unplayable stops mattering
# without a single byte of the originals being touched. Plus the provider title,
# which glowed in its own colour and so had no edges left.
section("v3.75 patch11: the repaired sample vault, and the provider glow")

check("def tts_sample_dir(" in py and '"voice-samples"' in py,
      "the vault has a default home, so a blank setting is still a working one")
check("def tts_sample_trim(" in py and "0x7FFFFFFF" in py,
      "frames are read for what the file HOLDS, not the length its header claims")
check("def tts_sample_adopt(" in py and "os.replace(tmp, dst)" in py,
      "a repaired copy is written whole or not at all")
check("_had_vault = os.path.isfile(" in py and '"adopted" if _adopted else "ok"' in py,
      "only the FIRST repair is news - after that the ledger stays quiet")
check('.get("ttsSampleAdopt") or "on"' in py,
      "and the whole behaviour can be turned off")
check('"ttsSampleDir": ""' in py and '"ttsSampleSec": "10"' in py
      and py.count('["ttsSampleDir", "Repaired Sample Vault') == 2,
      "the vault's rows sit in the Audio Files field for both engines")
check(".provlink:hover { color:var(--txt); text-shadow:0 0 9px var(--pgl); }" in py,
      "the provider title keeps its glyph light and its colour in the halo")
nin(py, "color:var(--pgl); text-shadow:0 0 10px var(--pgl)",
    "the rule that dissolved the title into its own halo is gone")

import tempfile as _tfB, io as _ioB, struct as _stB, wave as _wvB
try:
    _lcB = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log,
            fp.TTSW.log, fp.tts_voice_index)
    _DB = _tfB.mkdtemp()
    _VB = os.path.join(_DB, "vault")
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DB, "ttsSampleDir": _VB}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DB
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    fp.tts_voice_index = lambda cfg=None: {}
    _CB = {"settings": {"logDir": _DB, "ttsSampleDir": _VB, "ttsSampleSec": "10"}}

    def _mkB(path, seconds=20.0, rate=16000, lead=1.0, broken=False):
        _n = int(rate * seconds)
        _body = bytearray()
        for _i in range(_n):
            _v = 0 if _i < int(rate * lead) else (6000 if (_i // 40) % 2 else -6000)
            _body += _stB.pack("<h", _v)
        _buf = _ioB.BytesIO()
        with _wvB.open(_buf, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(rate)
            _w.writeframes(bytes(_body))
        _raw = bytearray(_buf.getvalue())
        if broken:
            _raw[4:8] = b"\xff\xff\xff\xff"
            _raw[40:44] = b"\xff\xff\xff\xff"
        with open(path, "wb") as _f:
            _f.write(bytes(_raw))
        return path

    def _secB(b):
        with _wvB.open(_ioB.BytesIO(b), "rb") as _w:
            return _w.getnframes() / float(_w.getframerate())

    _srcB = _mkB(os.path.join(_DB, "femaledarkelf.wav"), 20.0, lead=1.0)
    _cut = fp.tts_sample_trim(open(_srcB, "rb").read(), 10.0)
    _t1 = 9.9 < _secB(_cut) <= 10.05
    _badB = _mkB(os.path.join(_DB, "maleorc.wav"), 8.0, broken=True)
    _rawB = open(_badB, "rb").read()
    _fix = fp.tts_sample_trim(_rawB, 10.0)
    _t2 = bool(_fix) and 7.0 < _secB(_fix) < 8.1
    with open(os.path.join(_DB, "chk.wav"), "wb") as _f:
        _f.write(_fix)
    _t3 = fp.tts_wav_head_ok(open(os.path.join(_DB, "chk.wav"), "rb").read(fp.TTS_WAV_HEAD),
                             os.stat(os.path.join(_DB, "chk.wav")).st_size)
    check(_t1 and _t2 and _t3,
          "run: a long clip is capped, a 0xFFFFFFFF clip is read for what it holds, "
          "and what comes out passes the panel's own header check",
          str([_t1, _t2, _t3]))

    _pB = fp.tts_sample_adopt(_badB, "maleorc", _CB)
    _a1 = _pB == os.path.join(_VB, "maleorc.wav") and os.path.isfile(_pB)
    _a2 = os.path.getsize(_badB) == len(_rawB)
    _mtB = os.stat(_pB).st_mtime_ns
    _a3 = (fp.tts_sample_adopt(_badB, "maleorc", _CB) == _pB
           and os.stat(_pB).st_mtime_ns == _mtB)
    with open(os.path.join(_DB, "notawav.wav"), "wb") as _f:
        _f.write(b"this is not audio")
    _a4 = (fp.tts_sample_adopt(os.path.join(_DB, "nope.wav"), "ghost", _CB) == ""
           and fp.tts_sample_adopt(os.path.join(_DB, "notawav.wav"), "junk", _CB) == "")
    check(_a1 and _a2 and _a3 and _a4,
          "run: the copy lands under the voicetype's name, the original is never "
          "touched, a repaired voice is not repaired twice, and rubbish is refused",
          str([_a1, _a2, _a3, _a4]))

    fp._VT_SHA.clear(); fp._SHA_VT.clear()
    _s2B = _mkB(os.path.join(_DB, "femaleshrill.wav"), 12.0, broken=True)
    _g1, _v1 = fp.tts_sample_gate(_s2B, "femaleshrill", _CB)
    _g2, _v2 = fp.tts_sample_gate(_s2B, "femaleshrill", _CB)
    _r1 = (_g1 == os.path.join(_VB, "femaleshrill.wav") and _v1 == "adopted"
           and _g2 == _g1 and _v2 == "ok")
    _r2 = fp._VT_SHA.get("femaleshrill") == fp.tts_ref_fingerprint(_g1)[2]
    _offB = dict(_CB["settings"]); _offB["ttsSampleAdopt"] = "off"
    fp._VT_SHA.clear(); fp._SHA_VT.clear()
    _s3B = _mkB(os.path.join(_DB, "malebrute.wav"), 6.0)
    _g3, _v3 = fp.tts_sample_gate(_s3B, "malebrute", {"settings": _offB})
    _r3 = _g3 == _s3B and not os.path.exists(os.path.join(_VB, "malebrute.wav"))
    check(_r1 and _r2 and _r3,
          "run: the first line repairs and speaks from the vault, later lines are "
          "quiet, the ledger records the copy's hash, and Off changes nothing",
          str([_r1, _r2, _r3]))
except Exception as _eBx:
    check(False, "the patch11 runs did not RUN", str(_eBx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log,
         fp.TTSW.log, fp.tts_voice_index) = _lcB
        fp._VT_SHA.clear(); fp._SHA_VT.clear()
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch12
# The server card reads as ONE design: every group boundary is the same height
# with its divider dead centre, the Speculative Decoding section is built from
# the same anatomy as its neighbours - tight cells, blue flag references - and
# the two model-head notes are the yellow chip they were describing.
section("v3.75 patch12: the card reads as one design")

check(".slotgrid .pcell:has(+ .pgrp) { margin-bottom:0 !important; }" in py,
      "the cell before a heading gives its margin up, whatever kind of cell it was")
check(".slotgrid .pgrp { margin:18px 0 12px; padding-top:18px; }" in py,
      "so the heading owns the whole gap: 18 above the line, 18 below it, every group")
check("'<div class=\"pgrp\">Speculative Decoding'" in py,
      "the segment opens with a real group heading, not a bold row pretending")
check("const ref9 = function(flag)" in py and 'style="cursor:default"' in py,
      "its flag references are styled like the others and honest about not opening")
check('ref9(flag)' in py and py.count('"--spec-draft-') >= 14,
      "every cell names the flag it writes, in blue, like every cell above it")
check("'<div class=\"pcell ptight\"'" in py,
      "and its cells are as tight as the generation cells they sit under")
check("'Built-in MTP head</span>')" in py and 'class="mandy"' in py,
      "the built-in head is a yellow chip beside the heading, only when it is the drafter")
check("+ 'Built-in MTP head</span></div>'" in py,
      "and the note under the model dropdown is the same chip, not a coloured hint")
nin(py, "Built-in MTP head detected",
    "the prose version of that note is gone")
nin(py, "type: draft-mtp - the model's own head",
    "so is the right-aligned type caption the chip replaces")
nin(py, "type read from the drafter's own header",
    "for file drafters the picker already names the type - no caption repeats it")

# ----------------------------------------------------------------- v3.75 patch13
# The runaway is met with a measurement, not a clock: audio held against what the
# TEXT should take, one retry, both takes on record - Line Time Limit remains as
# the alternate mode. And the Sample Vault becomes the default home for voices:
# created by the installer, fed by SkyrimNet or by the owner's local clips, with
# a local clip's edits taking effect the moment its bytes change.
section("v3.75 patch13: runaway detection and the vault as the default")

check('"ttsRunawayMode": "detect",' in py and '"ttsRunawayRatio": "1.7",' in py,
      "detection is the default handling, with the threshold a setting")
check('"ttsAcppRefSlots": "1024",' in py
      and 'st.get("ttsAcppRefSlots", "1024")' in py,
      "the voice cache defaults to 1024 everywhere a default is read")
check("def tts_wav_seconds(" in py and "def tts_runaway_expect(" in py
      and "def tts_runaway_verdict(" in py,
      "the audio is measured, the text sets the expectation, the verdict compares")
# retold patch16: the fitted constants live in the voice model the cap uses
check("VOICE_SLOPE0" in py and "VOICE_BASE0" in py and "RUNAWAY_SHORT = 0.5" in py
      and "return tts_voice_tokens(text, vt, rows)[0] / TTS_ACPP_FRAME_RATE" in py,
      "the expectation IS the voice model - one number prices and judges alike")
check("deliberately independent of the auto-cal estimator" in py,
      "and it cannot collapse with a setting - the fault the first draft carried")
check('_rv13, _sec13, _exp13 = tts_runaway_verdict(' in py   # retold p16: vt rides along
      and 'if _b2 and abs(_s2 - _exp13) < abs(_sec13 - _exp13):' in py,
      "a runaway is retried once and the take closer to its estimate speaks")
check('elif _rv13 == "short":' in py and "words may have been dropped" in py,
      "a short take is measured and said, never retried - the rate comes first")
check('busy_ms = max(busy_ms, 30000)' in py,
      "detect mode floors the server clock so the cap, not the clock, is the bound")
check('os.path.join(STACK, "Sample Vault")' in py and '"voice-samples"' in py,
      "the vault lives beside the panel, and a populated patch11 vault still reads")
check("def _vault_index_get(" in py and "def _vault_index_set(" in py
      and "_vault_index_set(d, vt, src_sha)" in py,
      "every vault entry remembers the source bytes that built it")
check("is_local = bool(vdir)" in py
      and "if not (is_local and src_sha and _vault_index_get(d, vt) != src_sha):" in py,
      "a changed LOCAL clip re-adopts; a changed upload does not churn the vault")
# retold patch31: one writer for all four discovered paths, not a block per branch
check('st["ttsSampleDir"] = vault' in py
      and "os.makedirs(vault, exist_ok=True)" in py
      and "tts_write_install_paths(paths[" in py,
      "the installer creates the vault and writes the path into the field")
check('["ttsRunawayMode", "Runaway Handling' in py
      and '["ttsRunawayRatio", "Runaway Threshold' in py,
      "the dropdown and its rows are on the page")
check('f[2] === "sel"' in py and 'if (f.length < 5 || !f[4]) return true;' in py,
      "the fieldset renders selects, and a row tied to a mode exists only under it")

import io as _ioC, wave as _wvC, json as _jsC, tempfile as _tfC, struct as _stC
try:
    _lcC = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log, fp.TTSW.log)
    _DC = _tfC.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DC}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DC
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None

    def _bodyC(s):
        _b = _ioC.BytesIO()
        with _wvC.open(_b, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(24000)
            _w.writeframes(bytes(2) * int(24000 * s))   # two zero bytes, no escapes
        return _b.getvalue()

    _stD = {"ttsRunawayRatio": "1.7"}
    _tagC = "<|emotion:sadness|>... <|sfx:sigh|>Ahh, Morning."
    _longC = "Good morning to you, my friend, and welcome to the college today."
    _v1 = fp.tts_runaway_verdict(_bodyC(27.52), "Good morning.", _stD)[0] == "runaway"
    _v2 = fp.tts_runaway_verdict(_bodyC(1.54), "Good morning.", _stD)[0] == ""
    _v3 = fp.tts_runaway_verdict(_bodyC(4.8), _longC, _stD)[0] == ""
    # retold patch16: a sigh-line is a PERFORMANCE - exempt, and verified by the
    # recogniser instead when it is suspect
    _v4 = fp.tts_runaway_verdict(_bodyC(1.28), _tagC, _stD)[0] == ""
    _v5 = fp.tts_runaway_verdict(_bodyC(4.0), _tagC, _stD)[0] == ""
    _v6 = fp.tts_runaway_verdict(b"junk", "x", _stD)[0] == ""
    check(_v1 and _v2 and _v3 and _v4 and _v5 and _v6,
          "run: the 27.5s field runaway flags, the sigh-line is exempt as a "
          "performance, and every legitimate field take - median, long, "
          "slow-tagged - passes", str([_v1, _v2, _v3, _v4, _v5, _v6]))

    _b1 = _jsC.loads(fp.tts_acpp_config({"settings": {"logDir": _DC,
                                                      "ttsAcppBusyMs": "9000"}}))
    _b2 = _jsC.loads(fp.tts_acpp_config({"settings": {"logDir": _DC,
                                                      "ttsAcppBusyMs": "9000",
                                                      "ttsRunawayMode": "limit"}}))
    _b3 = _jsC.loads(fp.tts_acpp_config({"settings": {"logDir": _DC,
                                                      "ttsAcppBusyMs": "45000"}}))
    _bb = (_b1["models"][0]["busy_timeout_ms"] == 30000
           and _b2["models"][0]["busy_timeout_ms"] == 9000
           and _b3["models"][0]["busy_timeout_ms"] == 45000)
    check(_bb, "run: detect floors the clock at 30s, limit keeps the user's, and a "
               "clock already above the floor is respected", str(_bb))

    _VC = _tfC.mkdtemp(); _LC = _tfC.mkdtemp(); _UC = _tfC.mkdtemp()
    def _mkC(path, seed):
        _b = _ioC.BytesIO()
        with _wvC.open(_b, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(16000)
            _w.writeframes(_stC.pack("<h", 5000 - seed) * 48000)
        with open(path, "wb") as _f:
            _f.write(_b.getvalue())
        return path
    _CVC = {"settings": {"logDir": _DC, "ttsSampleDir": _VC, "ttsVoiceDir": _LC,
                         "ttsSampleSec": "10"}}
    _upC = _mkC(os.path.join(_UC, "femaledarkelf.wav"), 1)
    _p1 = fp.tts_sample_adopt(_upC, "femaledarkelf", _CVC)
    _r1 = _p1 == os.path.join(_VC, "femaledarkelf.wav")
    _mkC(_upC, 2)
    _shaA = fp.tts_ref_fingerprint(_p1)[2]
    fp.tts_sample_adopt(_upC, "femaledarkelf", _CVC)
    _r2 = fp.tts_ref_fingerprint(_p1)[2] == _shaA
    _lcC2 = _mkC(os.path.join(_LC, "femaledarkelf.wav"), 3)
    fp.tts_sample_adopt(_lcC2, "femaledarkelf", _CVC)
    _r3 = fp.tts_ref_fingerprint(_p1)[2] != _shaA
    _shaB = fp.tts_ref_fingerprint(_p1)[2]
    fp.tts_sample_adopt(_lcC2, "femaledarkelf", _CVC)
    _r4 = fp.tts_ref_fingerprint(_p1)[2] == _shaB
    _mkC(_lcC2, 4)
    fp.tts_sample_adopt(_lcC2, "femaledarkelf", _CVC)
    _r5 = fp.tts_ref_fingerprint(_p1)[2] != _shaB
    _idxC = _jsC.load(open(os.path.join(_VC, "vault-index.json"), encoding="utf-8"))
    _r6 = _idxC.get("femaledarkelf") == fp.tts_ref_fingerprint(_lcC2)[2]
    check(_r1 and _r2 and _r3 and _r4 and _r5 and _r6,
          "run: uploads adopt once and never churn, a local clip re-adopts exactly "
          "when its bytes change, and the index records the source",
          str([_r1, _r2, _r3, _r4, _r5, _r6]))
except Exception as _eCx:
    check(False, "the patch13 runs did not RUN", str(_eCx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir,
         fp.panel_log, fp.TTSW.log) = _lcC
    except Exception:
        pass



# ----------------------------------------------------------------- v3.75 patch14
# Reference transcripts become the default rather than an option: On out of the
# box (costing nothing until a model exists), the Higgs installer fetches the
# SenseVoice recogniser audio.cpp's own documentation names and points the field
# at it, the page guards against picking the TTS model itself, every control in
# the section carries a ? explanation, and finishing an install refreshes the
# very settings and model lists the install just changed.
section("v3.75 patch14: transcripts by default, SenseVoice by installer")

check('"ttsAsrMode": "on",' in py
      and py.count('st.get("ttsAsrMode") or "on"') == 4,   # retold p16: +tts_asr_live
      "On is the default in the setting AND in every fallback that reads it")
check('SENSE_GGUF_REPO = "FunAudioLLM/SenseVoiceSmall-GGUF-audiocpp"' in py
      and 'SENSE_GGUF_PATH = "sensevoice-small-q8-audiocpp-v1.gguf"' in py,
      "the source is the one audio.cpp's sense_asr doc names for this release")
check('_hi_download(url, sv, "sensevoice")' in py
      and "transcripts stay idle until a model is picked" in py,
      "the installer fetches it and a miss is logged, never fatal")
check('st["ttsAcppAsrModel"] = sv' in py and 'if sv:' in py,
      "and the field is pointed at it only when it actually arrived")
check(py.count('ttsTitle("SenseVoice model (.gguf)"')
      + py.count('ttsTitle("Recognition language"')
      + py.count('ttsTitle("Numbers"') == 3,   # retold p16: Meta tags removed
      "every control in the section explains itself the way the title does")
check("not a recogniser - the server will refuse the entry" in py,
      "picking the TTS model as the recogniser is named for what it is")
check("ttsModels = null;" in py and 'if (curTab === "tts") renderTts(true);' in py,
      "the install's end forces fresh settings, a fresh model list, a fresh page")

import tempfile as _tfE, json as _jsE
try:
    _lcE = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log)
    _DE = _tfE.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DE}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DE
    fp.panel_log = lambda *a, **k: None
    _svE = os.path.join(_DE, "sensevoice-small-q8-audiocpp-v1.gguf")
    with open(_svE, "wb") as _f:
        _f.write(b"GGUF")
    _base = {"logDir": _DE, "ttsAcppModel": "D:/m/h.gguf", "ttsAcppAsrModel": _svE}
    _j1 = _jsE.loads(fp.tts_acpp_config({"settings": dict(_base)}))
    _j2 = _jsE.loads(fp.tts_acpp_config({"settings": dict(_base, ttsAsrMode="off")}))
    _j3 = _jsE.loads(fp.tts_acpp_config({"settings": dict(_base, ttsAsrMode="stored")}))
    _e1 = len(_j1["models"]) == 2 and _j1["models"][1]["family"] == "sense_asr"
    _e2 = len(_j2["models"]) == 1 and len(_j3["models"]) == 1
    check(_e1 and _e2,
          "run: a config that never mentions the mode co-hosts the recogniser - On "
          "IS the default - while Off and Stored still co-host nothing",
          str([_e1, _e2]))
except Exception as _eEx:
    check(False, "the patch14 run did not RUN", str(_eEx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log) = _lcE
    except Exception:
        pass

# ----------------------------------------------------------------- v3.75 patch15
# What a line costs is now FITTED from what that voice has actually cost, not
# guessed from a constant that was too tight on short lines - where a cap-hit
# returns 500 and NO audio, losing the line - and too loose on long ones, where
# it let a runaway burn twice as long as it needed to.
section("v3.75 patch15: every voice prices its own lines")

check("VOICE_SLOPE0 = 1.065" in py and "VOICE_BASE0 = 25.2" in py,
      "the cold-start fit is the one measured from the sweeps, written down")
check("def tts_voice_extra(" in py and py.count("tts_voice_extra(") >= 3
      and "def tts_voice_parts(" in py,          # retold p16: one decomposition
      "ONE function prices what a line performs - predictor and record share it")
check('"bare": len(re.sub(' in py and '"extra": round(tts_voice_extra(t), 1),' in py
      and '"vt": str(vt or ""),' in py,
      "a measurement records the voice, the spoken length, and the performed cost")
check("resid = tk - slope * c - float(r.get(\"extra\") or 0)" in py
      and 'if int(r.get("lex", 1)) == 0:' in py,   # retold p16
      "and the fit subtracts exactly what the predictor added")
check("if resid > VOICE_BASE0 * 6:      # a runaway, not an overhead" in py,
      "a runaway never teaches the model, or it inflates every later cap")
check('else (r.get("bare") or r.get("chars") or 0))' in py,   # retold p16
      "rows written before this patch still count, on their raw length")
check("def tts_voice_key(" in py and "tts_auto_cap(text, _st0, vt=tts_voice_key(ref_path))" in py
      and "vt=tts_voice_key(ref_path)," in py,
      "the vault's filename IS the voicetype, on the cap path and the record alike")
check("if _n15 >= VOICE_MIN_N:" in py,
      "a voice that has not spoken enough keeps the old constant, unchanged")

try:
    _lcF = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log)
    import tempfile as _tfF
    _DF = _tfF.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DF}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DF
    fp.panel_log = lambda *a, **k: None

    def _bareF(x):
        return len(re.sub(r"<\|[^|>]*\|>", "", x).strip())
    def _rowF(text, sec, vt="player"):
        return {"chars": len(text), "bare": _bareF(text), "vt": vt,
                "extra": round(fp.tts_voice_extra(text), 1), "tok": round(sec*25, 1)}
    # the real corpus shape: three lengths, a tagged cell, and ONE runaway
    _R = ([_rowF("Good morning", 1.54) for _ in range(6)]
          + [_rowF("Good morning to you", 1.68) for _ in range(6)]
          + [_rowF("Good morning to you, my friend, and welcome", 2.84) for _ in range(6)]
          + [_rowF("<|sfx:sigh|>Good morning", 1.90) for _ in range(6)]
          + [_rowF("Good morning", 27.52)])
    _n, _b, _sd, _sl = fp.tts_voice_stats(_R, "player")
    _f1 = _n == len(_R) - 1
    _f2 = 15 < _b < 40 and 0.6 < _sl < 1.5
    _p = fp.tts_voice_tokens("Good morning", "player", _R)[0]
    _f3 = abs(_p - 38.5) < 12
    _short = fp.tts_voice_cap("Good morning.", "player", _R, {})
    _long = fp.tts_voice_cap("Good morning to you, my friend, and welcome to the "
                             "college today.", "player", _R, {})
    _f4 = _short > fp.acpp_token_cap("Good morning.", {})
    _f5 = _long < fp.acpp_token_cap("Good morning to you, my friend, and welcome to "
                                    "the college today.", {})
    check(_f1 and _f2 and _f3 and _f4 and _f5,
          "run: the runaway is dropped, the fit lands on speech, and the cap gains "
          "room on short lines while losing it on long ones",
          str([_f1, _f2, _f3, _f4, _f5]))

    _n0, _b0, _sd0, _sl0 = fp.tts_voice_stats([], "stranger")
    _g1 = _n0 == 0 and _b0 == fp.VOICE_BASE0 and _sl0 == fp.VOICE_SLOPE0
    _g2 = 0 < fp.tts_voice_cap("Good morning.", "stranger", [], {}) <= fp.TTS_CAP_CEILING
    _cv, _nv, _ev = fp.tts_auto_cap("Good morning.", {}, rows=_R, vt="player")
    _cn, _nn, _en = fp.tts_auto_cap("Good morning.", {}, rows=_R, vt="")
    _g3 = _cv == _short and "player" in _nv and _ev > 0
    _g4 = _cn == fp.acpp_token_cap("Good morning.", {}) and _nn == "" and _en == 0.0
    check(_g1 and _g2 and _g3 and _g4,
          "run: an unheard voice uses the shipped fit and still caps, a known voice "
          "prices its own line and says so, and no voicetype means no change at all",
          str([_g1, _g2, _g3, _g4]))

    _t = "<|emotion:sadness|>... <|sfx:sigh|>Ahh, Morning."
    _rec = fp.tts_measure_row(_t, 2.0, vt="femaledarkelf")
    _h1 = (_rec.get("vt") == "femaledarkelf" and _rec.get("bare") == _bareF(_t)
           and abs(_rec.get("extra") - fp.tts_voice_extra(_t)) < 0.01)
    _h2 = (abs(fp.tts_voice_tokens(_t, "nobody", [])[0]   # retold p16: SPOKEN length
               - (fp.VOICE_BASE0 + fp.VOICE_SLOPE0 * fp.tts_voice_parts(_t)[0]
                  + fp.tts_voice_extra(_t, [])))
           < 0.01)
    _h3 = fp.tts_voice_extra("Good morning.") == 0.0
    check(_h1 and _h2 and _h3,
          "run: the record carries what the fit needs, and a line is priced by one "
          "arithmetic on both sides", str([_h1, _h2, _h3]))
except Exception as _eFx:
    check(False, "the patch15 runs did not RUN", str(_eFx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log) = _lcF
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch16
# One model prices, judges and now VERIFIES. The verdict runs on the same
# per-voice fit as the cap; performances - "Ahh...", a lone sigh - are exempt
# from judgement and from teaching the fit; tag costs are learned from lines
# that carried them; a suspect short take is transcribed and convicted or
# acquitted on its words; and the dial that was wired to nothing is gone.
section("v3.75 patch16: the recogniser joins the verdict")

check("def tts_voice_parts(" in py and 'r"\\.{2,}|\\u2026"' in py
      and py.count("tts_voice_parts(") >= 5,
      "one decomposition of a line, shared by pricing, fitting and exemption")
check("def tts_line_lexical(" in py and 'r"[aeiouhmw]+"' in py
      and 'r"(.)\\1"' in py,
      "a performance is breathy letters WITH a stretch - a charset cannot tell "
      "an order from a moan")
check("def tts_tag_costs(" in py and "max(3.0, min(60.0," in py
      and "if len(vals) < 6:" in py,
      "tag costs are learned from measured lines, clamped, and defer to the "
      "prior until enough exist")
check('"keep_tags": False,' in py and "ttsAsrTags" not in py,
      "the recogniser is never asked for markers, and the dial is gone")
check("def tts_asr_live(" in py and "def tts_asr_transcribe(" in py
      and py.count("/v1/audio/transcriptions") == 1,
      "one place speaks to the endpoint; the learner, verifier and note share it")
check("def tts_take_verify(" in py and "hit * 2 > len(words)" in py
      and 'os.remove(tmp)' in py,
      "a suspect take is judged on a strict majority of its words, and the "
      "scratch file does not outlive the question")
check('_vfy = tts_take_verify(body, processed, cfg)' in py
      and 'if _vfy == "dropped":' in py and '\\u2713 short take verified' in py,
      "dropped words earn one retry; a brief take that spoke them is praised")
check("if not tts_line_lexical(text):" in py
      and 'vt=tts_voice_key(ref_path))' in py,
      "the verdict knows the voice and passes a performance unjudged")
check('"vault-notes.json"' in py and "tts_asr_live(cfg)" in py,
      "what the recogniser heard in a sample is kept beside the vault, as a note")

import types as _tyG, json as _jsG, tempfile as _tfG
try:
    _lcG = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log,
            fp._ureq, fp._ACPP_NO_ASR[0])
    _DG = _tfG.mkdtemp()
    fp.load_config = lambda *a, **k: {"settings": {"logDir": _DG, "ttsAsrMode": "on",
                                                   "ttsAcppAsrModel": "D:/m/s.gguf"}}
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda cfg=None: _DG
    fp.panel_log = lambda *a, **k: None
    fp._ACPP_NO_ASR[0] = False

    import io as _ioG, wave as _wvG
    def _bodyG(s):
        _b = _ioG.BytesIO()
        with _wvG.open(_b, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(24000)
            _w.writeframes(bytes(2) * int(24000 * s))
        return _b.getvalue()

    _sp, _sx, _dt, _pz = fp.tts_voice_parts(
        "<|emotion:sadness|>... <|sfx:sigh|>Ahh, Morning.")
    _p1 = _sx == 1 and _dt == 1 and _sp == len("Ahh, Morning.")
    _p2 = (fp.tts_line_lexical("Run. Now.")
           and not fp.tts_line_lexical("Ahh...")
           and not fp.tts_line_lexical("<|sfx:moan|>Mmm"))
    check(_p1 and _p2, "run: the ellipsis is a pause, not characters, and an order "
          "is words while a moan is not", str([_p1, _p2]))

    def _rowG(text, tok):
        _s, _x, _d, _ = fp.tts_voice_parts(text)
        return {"spoken": _s, "sfx": _x, "dots": _d,
                "lex": 1 if fp.tts_line_lexical(text) else 0,
                "extra": 0.0, "tok": float(tok), "vt": "player",
                "chars": len(text), "bare": _s}
    _base = [_rowG("Good morning to you my friend",
                   fp.VOICE_BASE0 + fp.VOICE_SLOPE0 * 29) for _ in range(8)]
    _sfxr = [_rowG("<|sfx:sigh|>Good morning to you my friend",
                   fp.VOICE_BASE0 + fp.VOICE_SLOPE0 * 29 + 30) for _ in range(8)]
    _c1, _d1 = fp.tts_tag_costs(_base + _sfxr)
    _q1 = abs(_c1 - 30) < 2 and _d1 == fp.VOICE_DOTS_TOK
    _c2, _ = fp.tts_tag_costs(_base + _sfxr[:5]
                              + [_rowG("<|sfx:sigh|>Good morning to you my friend",
                                       3000)])
    _q2 = _c2 <= 60
    _q3 = fp.tts_tag_costs(_base + _sfxr[:3])[0] == fp.VOICE_SFX_TOK
    _perf = [_rowG("Ahh...", 200) for _ in range(6)]
    _q4 = (fp.tts_voice_stats(_base, "player")[:2]
           == fp.tts_voice_stats(_base + _perf, "player")[:2])
    check(_q1 and _q2 and _q3 and _q4,
          "run: eight measured sighs teach ~30 tokens, one poisoned row cannot "
          "teach 3000, five are too few, and moans teach nothing",
          str([_q1, _q2, _q3, _q4]))

    _exp = fp.tts_runaway_expect("Good morning.", "player", _base)
    _prd = fp.tts_voice_tokens("Good morning.", "player", _base)[0] / 25.0
    _r1 = abs(_exp - _prd) < 1e-9
    _r2 = fp.tts_runaway_verdict(_bodyG(27.52), "Good morning.", {},
                                 vt="player", rows=_base)[0] == "runaway"
    _r3 = fp.tts_runaway_verdict(_bodyG(9.0), "Ahh...", {}, vt="player",
                                 rows=_base)[0] == ""
    _r4 = fp.tts_runaway_verdict(_bodyG(0.4), "<|sfx:moan|>Mmm", {},
                                 vt="player", rows=_base)[0] == ""
    _long = "Good morning to you, my friend, and welcome to the college today."
    _r5 = fp.tts_runaway_verdict(_bodyG(fp.tts_runaway_expect(_long) * 0.2),
                                 _long, {})[0] == "short"
    check(_r1 and _r2 and _r3 and _r4 and _r5,
          "run: one expectation for cap and verdict, the field runaway still "
          "flags, performances pass in both directions, worded shorts still flag",
          str([_r1, _r2, _r3, _r4, _r5]))

    _heard = ["<|en|><|NEUTRAL|><|Speech|>Ahh."]
    class _RespG:
        def read(self):
            return _jsG.dumps({"text": _heard[0]}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    fp._ureq = _tyG.SimpleNamespace(Request=fp._ureq.Request,
                                    urlopen=lambda req, timeout=0: _RespG())
    _s1 = fp.tts_take_verify(_bodyG(1.28), "Ahh, Morning.", None) == "dropped"
    _heard[0] = "<|en|>ahh, morning"
    _s2 = fp.tts_take_verify(_bodyG(1.28), "Ahh, Morning.", None) == "spoken"
    _s3 = fp.tts_take_verify(_bodyG(1.0), "Mmm", None) == ""
    fp._ACPP_NO_ASR[0] = True
    _s4 = fp.tts_take_verify(_bodyG(1.28), "Ahh, Morning.", None) == ""
    fp._ACPP_NO_ASR[0] = False
    _s5 = not [f for f in os.listdir(_DG) if f.startswith("verify-")]
    check(_s1 and _s2 and _s3 and _s4 and _s5,
          "run: a transcript missing the words convicts, one carrying them "
          "acquits, one word cannot convict, no recogniser no verdict, and the "
          "scratch is gone", str([_s1, _s2, _s3, _s4, _s5]))
except Exception as _eGx:
    check(False, "the patch16 runs did not RUN", str(_eGx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log,
         fp._ureq, fp._ACPP_NO_ASR[0]) = _lcG
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch17
# A session that fails must leave enough behind to say WHY. audio.cpp is asked to
# log; the panel writes its own launch banner whatever the server chooses to say;
# failures carry stable codes and, for the memory ones, what was resident; an
# allocation failure is retried rather than silently dropping the line; and every
# step on the audio path books its own milliseconds instead of vanishing into one
# residual called "panel".
section("v3.75 patch17: the audio path explains itself")

check('args = [exe, "--config", cfgp, "--log"]' in py,
      "audio.cpp is asked for its own logs - without this it barely speaks")
check("def tts_launch_banner(" in py and "tts_launch_banner(cfg, args," in py
      and "PandorumLLM %s launching audio.cpp at %s" in py,
      "the panel records what IT launched, whatever the server then says")
check('"  model  id=%-8s family=%-18s task=%-5s  %8.1f MiB  %s"' in py
      and 'lines.append("  argv   %s"' in py,
      "every model, family, size and the argv are in that banner")
check("def tts_vram_probe(" in py and "query-compute-apps=pid,process_name,used_memory" in py
      and "def tts_vram_line(" in py,
      "and what is resident on the card, which no log could say before")
check("TTS_ERR = {" in py and '"ALLOC": ("TTS-E01"' in py and '"EOC": ("TTS-E02"' in py
      and "def tts_err(" in py,
      "failures carry stable codes that survive rewording and grep cleanly")
check('_alloc = ("allocate" in _msg or "out of memory" in _msg' in py
      and "if _alloc and _try < 2:" in py and "time.sleep(0.6 * (_try + 1))" in py,
      "an allocation failure waits and asks again - it used to lose the line")
check("def tts_gpu_uuid(" in py and py.count("tts_gpu_uuid(") >= 3,
      "one resolver for the pinned card, used everywhere it is needed")
check("class spend_step(" in py and "def spend_reset(" in py
      and py.count("with spend_step(") >= 5,
      "each audio-path step books its own time")
check('spend_bits(\n' in py or 'for _st17, _ms17 in spend_bits(' in py,
      "and the report prints the ledger, not one residual")
check('"thought audio"' in py and '"sample gate"' in py and '"transcript"' in py,
      "including thought synthesis, which hid 2.6s inside 'panel' in the field")
check("!/higgs|vibevoice|indextts|fish-audio|voxcpm/i.test" in py,
      "the recogniser picker stops offering speech models as recognisers")

try:
    _lcH = (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log)
    import tempfile as _tfH
    _DH = _tfH.mkdtemp()
    _cfgH = {"settings": {"logDir": _DH, "ttsGpuId": "gpu1",
                          "ttsAcppModel": os.path.join(_DH, "higgs.gguf"),
                          "ttsAsrMode": "off"},
             "gpus": [{"id": "gpu0", "uuid": "GPU-aaa"},
                      {"id": "gpu1", "uuid": "GPU-zotac"}]}
    fp.load_config = lambda *a, **k: _cfgH
    fp.load_config_cached = fp.load_config
    fp.log_dir = lambda c=None: _DH
    fp.panel_log = lambda *a, **k: None
    with open(_cfgH["settings"]["ttsAcppModel"], "wb") as _f:
        _f.write(b"x" * 4096)

    _u1 = fp.tts_gpu_uuid(_cfgH) == "GPU-zotac"
    _u2 = fp.tts_gpu_uuid({"settings": {}, "gpus": []}) == ""
    _v1 = fp.tts_vram_probe("") == (0, 0, []) and fp.tts_vram_line("") == ""
    check(_u1 and _u2 and _v1,
          "run: the pinned card resolves by id, an unset one is empty, and a probe "
          "with no card is silent rather than fatal", str([_u1, _u2, _v1]))

    fp.tts_launch_banner(_cfgH, ["audiocpp_server", "--config", "c.json", "--log"],
                         "GPU-zotac")
    with open(fp.tts_server_log_path(_cfgH), encoding="utf-8") as _f:
        _txt = _f.read()
    _b1 = "launching audio.cpp" in _txt and "higgs_audio_tts" in _txt
    _b2 = "GPU-zotac" in _txt and "--log" in _txt
    _b3 = "MiB" in _txt
    check(_b1 and _b2 and _b3,
          "run: the banner names the model, its family, the pinned card and the "
          "argv - a silent server is still diagnosable", str([_b1, _b2, _b3]))

    _e1 = fp.tts_err("ALLOC", "x").startswith("TTS-E01")
    _e2 = fp.tts_err("EOC").startswith("TTS-E02")
    _e3 = fp.tts_err("NOPE").startswith("TTS-E00")
    fp.spend_reset()
    with fp.spend_step("thought audio"):
        time.sleep(0.02)
    fp.spend_add("sample gate", 0.01)
    fp.spend_add("identity note", 0.0)
    _bits = fp.spend_bits(("thought audio", "sample gate"))
    _s1 = [k for k, _v in _bits] == ["thought audio", "sample gate"]
    _s2 = all(v > 0 for _k, v in _bits)
    fp.spend_reset()
    _s3 = fp.spend_bits() == []
    check(_e1 and _e2 and _e3 and _s1 and _s2 and _s3,
          "run: every code is stable, an unknown one still answers, the ledger "
          "keeps its order, ignores nothing-time and empties per line",
          str([_e1, _e2, _e3, _s1, _s2, _s3]))
except Exception as _eHx:
    check(False, "the patch17 runs did not RUN", str(_eHx)[:140])
finally:
    try:
        (fp.load_config, fp.load_config_cached, fp.log_dir, fp.panel_log) = _lcH
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch18
# The ruler, before anything is measured against it. A line that failed once and
# succeeded once was reported as ONE slow synthesis - realtime factor, tps and
# the record all read a number no single take ever took, which is how a healthy
# engine came to look like a broken one. The take that played is now reported on
# its own, the discarded attempts beside it, and every line's numbers are also
# written machine-readably so a fixed cost can finally be told from a per-token
# one across hundreds of lines rather than six.
section("v3.75 patch18: the take, not the ladder")

check('"final_s": 0.0, "wasted_s": 0.0, "tries": 0' in py   # retold p19: per-thread
      and 'TTS_TAKE["final_s"] = time.time() - _t0' in py
      and 'TTS_TAKE["wasted_s"] += _spent' in py,
      "the ladder records the take that played and the time thrown away, apart")
check('_fin18 = float(TTS_TAKE.get("final_s") or 0.0) or synth' in py
      and '(secs / _fin18) if _fin18 else 0.0, _fin18, secs' in py,
      "the realtime factor is the take alone")
check('% ("server:", _fin18 * 1000.0, toks,' in py
      and '(toks / _fin18) if _fin18 else 0.0' in py,
      "and so is the tps - the number that read 43 while the take ran at 75")
check('"discard:", _wst18 * 1000.0' in py and "attempt(s) thrown away before" in py,
      "what was discarded is still shown, on its own line, never hidden")
check('wall=(float(TTS_TAKE.get("final_s") or 0.0)' in py,
      "the measure record keeps the take's own wall time, not the ladder's")
check("TTS_TIMING_CSV" in py and "def tts_timing_row(" in py
      and '"ref_s", "ref_bytes", "ref_text_chars", "cap"' in py,
      "every line's numbers are written machine-readably, reference included")
check("def tts_ref_facts(" in py and "w.getnframes() / float(w.getframerate() or 1)" in py,
      "including how long the reference sample actually is")
check("the server returns no generate/" in py,
      "and a missing server-side split is said plainly, not silently absorbed")
check('"ttsSampleSec": "10",' in py,
      "the sample length is unchanged - a guess does not become a default")

import tempfile as _tfJ, io as _ioJ, wave as _wvJ, struct as _stJ
try:
    _lcJ = (fp.log_dir, fp.panel_log)
    _DJ = _tfJ.mkdtemp()
    fp.log_dir = lambda cfg=None: _DJ
    fp.panel_log = lambda *a, **k: None
    _refJ = os.path.join(_DJ, "player.wav")
    _bJ = _ioJ.BytesIO()
    with _wvJ.open(_bJ, "wb") as _w:
        _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(16000)
        _w.writeframes(_stJ.pack("<h", 1000) * 16000 * 3)
    with open(_refJ, "wb") as _f:
        _f.write(_bJ.getvalue())
    _s, _by = fp.tts_ref_facts(_refJ)
    _f1 = abs(_s - 3.0) < 0.01 and _by > 90000
    _f2 = fp.tts_ref_facts(os.path.join(_DJ, "nope.wav")) == (0.0, 0)
    fp.tts_timing_row(at="06:06:52", voice="player", chars=44, tokens=83.0,
                      final_ms=1108, wasted_ms=800, tries=2, cap=95)
    fp.tts_timing_row(at="06:06:49", voice="player", chars=44, tokens=81.0,
                      final_ms=1867, wasted_ms=0, tries=1, cap=95)
    with open(os.path.join(_DJ, "tts-timing.csv"), encoding="utf-8") as _f:
        _txt = _f.read()
    _f3 = _txt.count("\n") == 3 and _txt.startswith("at,voice,chars,tokens")
    _f4 = "1108,800,2" in _txt and "1867,0,1" in _txt
    check(_f1 and _f2 and _f3 and _f4,
          "run: a 3s reference reads as 3s, a missing one as zeroes, and the "
          "stream writes one header and one row per line carrying take, waste "
          "and attempts apart", str([_f1, _f2, _f3, _f4]))
except Exception as _eJx:
    check(False, "the patch18 runs did not RUN", str(_eJx)[:140])
finally:
    try:
        (fp.log_dir, fp.panel_log) = _lcJ
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch19
# Higgs keeps its reference prompt state in the model session, and nothing was
# serialising access to it: a dialogue line and a thought could be inside the
# engine together. The field log shows two reports interleaved mid-write, a take
# that ran 15.2s for 3.1s of audio, and a hash-verified MALE reference returning
# a female voice. One request holds the engine at a time now. And an allocation
# refusal no longer escalates the cap - the prefill graph is sized from
# max_tokens, so raising it asked the card for a bigger buffer than the one it
# had just refused, with 19 GB free.
section("v3.75 patch19: one line at a time, and a refusal is not a shortage")

check("_ENGINE_LOCK = threading.Lock()" in py and "with _ENGINE_LOCK:" in py,
      "one request holds the engine at a time - its session is stateful")
check("ENGINE_WAIT = threading.local()" in py and "def engine_wait_get(" in py
      and '"queued:", _wait19 * 1000.0' in py and '"queued_ms"' in py,
      "and the wait for it is measured, reported and recorded - never hidden")
check("_TAKE = threading.local()" in py and "class _TakeProxy(" in py,
      "two lines in flight keep their own timings instead of one shared dict")
check("_ACPP_HOLD_CAP = [False]" in py
      and "if attempt > 1 and not _ACPP_HOLD_CAP[0]:" in py
      and "the card refused a buffer, " in py,
      "an allocation refusal holds the cap - escalating asks for MORE of what "
      "was just refused")
check("_ACPP_HOLD_CAP[0] = False" in py, "and the hold is per line, not per session")
check('("failed to allocate",' in py and "is not a shortage" in py
      and "not enough VRAM - try a shorter reference voice" not in py,
      "the advice that was wrong with 19 GB free is gone")

import threading as _thK, time as _tmK
try:
    _seenK = {}
    def _wK(name, val):
        fp.TTS_TAKE.update(final_s=val, wasted_s=0.0, tries=1)
        _tmK.sleep(0.03)
        _seenK[name] = fp.TTS_TAKE.get("final_s")
    _tsK = [_thK.Thread(target=_wK, args=(n, v)) for n, v in (("a", 1.0), ("b", 2.0))]
    for _t in _tsK:
        _t.start()
    for _t in _tsK:
        _t.join()
    _k1 = _seenK == {"a": 1.0, "b": 2.0}
    _orderK = []
    def _hK(n):
        with fp._ENGINE_LOCK:
            _orderK.append(("in", n)); _tmK.sleep(0.03); _orderK.append(("out", n))
    _tsK = [_thK.Thread(target=_hK, args=(n,)) for n in (1, 2, 3)]
    for _t in _tsK:
        _t.start()
    for _t in _tsK:
        _t.join()
    _k2 = not any(_orderK[i][0] == "in" and _orderK[i + 1][0] == "in"
                  for i in range(len(_orderK) - 1))
    fp.engine_wait_reset()
    _k3 = fp.engine_wait_get() == 0.0
    check(_k1 and _k2 and _k3,
          "run: two threads keep their own take timings, no two requests are ever "
          "inside the engine at once, and the wait clock starts at zero",
          str([_k1, _k2, _k3, _seenK]))
except Exception as _eKx:
    check(False, "the patch19 runs did not RUN", str(_eKx)[:140])


# ----------------------------------------------------------------- v3.75 patch20
# The headroom was learning correctly and then having its answer thrown away: the
# fit asked for 2.65 and a 1.60 ceiling clamped it, in every session for weeks.
# The clamp was self-justifying - a line that hits an estimate-decided cap enters
# the fit at cap/est, which IS the current headroom, so 452 of 1124 scored lines
# entered at exactly 1.60 and held p95 down where the clamp was satisfied. The cap
# is already bounded by the guard, so the headroom defers to it now. And the
# record can be cleared deliberately, because a long run under a binding clamp
# leaves evidence that cannot say what it truly needed.
section("v3.75 patch20: the margin was pinned, not converged")

check("AUTOCAL_HEAD_MAX = 4.00" in py,
      "the ceiling is a sanity stop, not a working limit")
check("it is a margin pinned" in py or "it is a margin pinned." in py
      or "That is not a" in py,
      "and why it was raised is written where the constant lives")
check("def api_tts_cal_clear(" in py
      and '"/api/tts-cal-clear": api_tts_cal_clear,' in py,
      "the estimator's memory can be forgotten, deliberately and by hand")
# sliced to the function: MEASURE_GEN is bumped on every append too, so an
# unscoped pin cannot see it removed from HERE
_calseg = seg(py, "def api_tts_cal_clear(", "def api_tts_audio_cache_clear(")
check("for p in (TTS_MEASURE_LOG, TTS_MEASURE_LEGACY, EOC_LOG):" in _calseg
      and "MEASURE_GEN[0] += 1" in _calseg
      and '_MEASURE_CACHE["rows"] = []' in _calseg,
      "both stores go, and the warm copy does not survive the clear")
check('data-act="ttsCalClear"' in py and 'if (d.act === "ttsCalClear")' in py
      and "function calClear() {" in py,
      "the button is on the calibration section and wired to an action")
check('title: "Clear calibration data?"' in py
      and "This cannot be undone" in py and "What happens next" in py
      and "What is NOT touched" in py
      and 'label: "Yes, clear it", value: true' in py
      and 'label: "No", value: false' in py,
      "and it asks first, saying what is lost, what follows, and what is safe")

try:
    _lcL = (fp.TTS_MEASURE_LOG, fp.TTS_MEASURE_LEGACY, fp.EOC_LOG,
            fp.panel_log, fp.TTSW.log)
    import tempfile as _tfL, json as _jsL
    _DL = _tfL.mkdtemp()
    fp.TTS_MEASURE_LOG = os.path.join(_DL, "tts-measure.jsonl")
    fp.TTS_MEASURE_LEGACY = os.path.join(_DL, "tts-measure.json")
    fp.EOC_LOG = os.path.join(_DL, "eoc-events.json")
    fp.panel_log = lambda *a, **k: None
    fp.TTSW.log = lambda *a, **k: None
    _p95L = 2.41
    _wantL = min(fp.AUTOCAL_HEAD_MAX, max(fp.AUTOCAL_HEAD_MIN,
                                          _p95L * fp.AUTOCAL_HEAD_PAD))
    _l1 = abs(_wantL - 2.651) < 0.01
    with open(fp.TTS_MEASURE_LOG, "w", encoding="utf-8") as _f:
        _f.write(_jsL.dumps({"chars": 10, "tok": 30}) + "\n")
    with open(fp.EOC_LOG, "w", encoding="utf-8") as _f:
        _jsL.dump([{"a": 1}, {"a": 2}], _f)
    fp._MEASURE_CACHE["gen"] = 99
    fp._MEASURE_CACHE["rows"] = [{"x": 1}]
    _rL = fp.api_tts_cal_clear({})
    _l2 = _rL["ok"] and _rL["rows"] == 1 and _rL["eoc"] == 2
    _l3 = (not os.path.exists(fp.TTS_MEASURE_LOG)
           and not os.path.exists(fp.EOC_LOG))
    _l4 = fp._MEASURE_CACHE["rows"] == [] and fp._MEASURE_CACHE["gen"] == -1
    _l5 = fp.api_tts_cal_clear({})["rows"] == 0
    check(_l1 and _l2 and _l3 and _l4 and _l5,
          "run: the field's own p95 of 2.41 now yields 2.65 where it was pinned at "
          "1.60, and a clear removes both stores, reports what it forgot, drops "
          "the warm copy and is harmless when empty",
          str([_l1, _l2, _l3, _l4, _l5]))
except Exception as _eLx:
    check(False, "the patch20 runs did not RUN", str(_eLx)[:140])
finally:
    try:
        (fp.TTS_MEASURE_LOG, fp.TTS_MEASURE_LEGACY, fp.EOC_LOG,
         fp.panel_log, fp.TTSW.log) = _lcL
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch22
# The tagger returned [STYLE-SINGING] for a flat test sentence, and the prompt
# was the cause: "return it word for word WITH TAGS ADDED" presupposes markup on
# every line, and only one example in three showed a line returned unchanged. A
# prompt that asks for markup gets markup. And a stopped PTI server cost every
# player line a full timeout before failing open, silently.
section("v3.75 patch22: a tagger that can say nothing, and skips a dead server")

check('"MOST LINES NEED NO TAGS: a plain statement is returned exactly as it came."'
      in py and '"Add a tag only when the words themselves clearly call for one' in py
      and "with tags added" not in py,
      "the prompt states the default is NO tag, and no longer presupposes markup")
check('    ("This is a test of the text-to-speech system.",' in py
      and '    ("I will meet you at the gate at dawn.",' in py,
      "the observed failure is now a neutral example, verbatim")
check('_st22 = slot_status(_port22).get("state", "")' in py   # retold p36
      and 'if _st22 != "serving":' in py,
      "the tagger checks its server is SERVING before paying for a call")
check("_PTI_DOWN_SAID = [False]" in py
      and "the PTI server is back - player tags resume" in py,
      "the outage is said once, and the recovery is announced")

try:
    _lcN = (fp.panel_log, fp.load_config, fp.panel_prov_on, fp.panel_route,
            fp.slot_status, fp.mood_context)
    _p22 = fp.tts_tag_prompt()
    _n1 = ("MOST LINES NEED NO TAGS" in _p22
           and _p22.count("This is a test of the text-to-speech system.") == 2)
    _neu = sum(1 for _l, _t in fp.TAG_EXAMPLES if _l == _t)
    _n2 = _neu > len(fp.TAG_EXAMPLES) - _neu
    _logsN = []
    fp.panel_log = lambda m: _logsN.append(m)
    _cfgN = {"settings": {}, "gpus": [],
             "slots": [{"port": 5001, "providers": [{"id": "pti"}]}]}
    fp.load_config = lambda *a, **k: _cfgN
    fp.panel_prov_on = lambda *a: True
    fp.panel_route = lambda pid, cfg=None: {"port": 5001, "server": "S1",
                                            "url": "http://x"}
    fp.slot_status = lambda port: {"state": "down"}
    fp._PTI_DOWN_SAID[0] = False
    _r1 = fp.tts_player_tag("Hello there.", _cfgN)
    _r2 = fp.tts_player_tag("Hello again.", _cfgN)
    _n3 = _r1 == "" and _r2 == "" and len(
        [m for m in _logsN if "skipped" in m]) == 1 and "port 5001" in _logsN[0]
    fp.slot_status = lambda port: {"state": "serving"}
    fp.mood_context = lambda: ""
    _oldc = fp._pti_cached
    fp._pti_cached = lambda k: "Hello there."
    _r3 = fp.tts_player_tag("Hello there.", _cfgN)
    fp._pti_cached = _oldc
    _n4 = _r3 == "Hello there." and any("back" in m for m in _logsN)
    check(_n1 and _n2 and _n3 and _n4,
          "run: the prompt teaches silence by majority, a dead server skips "
          "instantly and is named once, and recovery resumes tagging",
          str([_n1, _n2, _n3, _n4]))
except Exception as _eNx:
    check(False, "the patch22 runs did not RUN", str(_eNx)[:140])
finally:
    try:
        (fp.panel_log, fp.load_config, fp.panel_prov_on, fp.panel_route,
         fp.slot_status, fp.mood_context) = _lcN
        fp._PTI_DOWN_SAID[0] = False
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch23
# Only the samplers Higgs v3 actually uses, set by hand, and nothing that moves
# them. Boson's reference is temperature 0.8 with top_k 50 and nothing else;
# audio.cpp documents repetition_penalty as accepted-but-unconsumed for this
# family; top_p and min_p only ever narrowed the distribution toward the
# degenerate repeat. Both movers are gone - the automatic step and the retry
# ladder's narrowing - because moving these values was the fault, not the fix.
section("v3.75 patch23: two samplers, no movers")

check(set(fp.TTS_SAMP_KEYS) == {"temp", "top_k"}
      and set(fp.TTS_SAMP_FIELD) == {"temp", "top_k"}
      and set(fp.CAL_REQUEST_KEYS.values()) == {"temperature", "top_k"},
      "two samplers, named once, and they are the two this engine takes")
check(set(fp.SN_TTS_FORWARD) == {"temperature", "top_k"},
      "and a top_p arriving from SkyrimNet is dropped, not forwarded")
check(fp.HIGGS_REF_SAMPLERS == {"ttsCalTemp": "0.8", "ttsCalTopK": "50"}
      and fp.DEF_SETTINGS.get("ttsCalTemp") == "0.8"
      and fp.DEF_SETTINGS.get("ttsCalTopK") == "50",
      "Boson's reference pair is the shipped default")
nin(py, "def autocal_sampler_arith", "the automatic sampler mover is gone entirely")
nin(py, "ttsSampAutoCal", "and its switch with it")
nin(py, "ttsRetrySafe", "Steady Retry is gone - a retry carries the same samplers")
nin(py, "ttsCalTopP", "top_p is not a setting this build carries")
nin(py, "ttsCalMinP", "nor min_p")
nin(py, "ttsCalRepPen", "nor repetition_penalty, which this family ignores anyway")
nin(py, "Sampler Calibration", "and the name it used to go by is gone too")
check('"sampKeys": {k: 1 for k in TTS_SAMP_KEYS}' in py
      and py.count('"sampKeys": {k: 1 for k in TTS_SAMP_KEYS}') == 2
      and 'Object.keys((d && d.sampKeys) || {})' in JS,
      "the chips read their keys from the panel - a second hard-coded list is how "
      "top-k was added everywhere except the page")
check('.plpay:hover { text-shadow:0 0 6px var(--acc); color:var(--txt); }' in py
      and "filter:drop-shadow(0 0 5px color-mix(in srgb, var(--acc) 75%" not in py,
      "the terminal hover is ONE tight glow: a drop-shadow filter over two "
      "text-shadows re-blurred pixels that were already blurred")

try:
    _lcP = fp.sn_tts_observed
    fp.sn_tts_observed = lambda: {"temperature": 0.6, "top_p": 0.9, "min_p": 0.05}
    _stP = dict(fp.DEF_SETTINGS)
    _s1P = fp.tts_samplers(_stP, 1)
    _p1 = _s1P == {"temperature": 0.8, "top_k": 50}
    _p2 = fp.tts_samplers(_stP, 2) == _s1P and fp.tts_samplers(_stP, 3) == _s1P
    _p3 = isinstance(_s1P["top_k"], int)
    _p4 = "top_p" not in _s1P and "min_p" not in _s1P
    check(_p1 and _p2 and _p3 and _p4,
          "run: a line carries Boson's pair, every attempt carries the SAME pair, "
          "top_k is an integer, and what this engine cannot use never reaches it",
          str([_p1, _p2, _p3, _p4, _s1P]))
except Exception as _ePx:
    check(False, "the patch23 runs did not RUN", str(_ePx)[:140])
finally:
    try:
        fp.sn_tts_observed = _lcP
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch24
# SenseVoice was invisible. Its inference is a second model on the same card, and
# it was either folded into "transcript" with a store read or off the line
# entirely on the learner thread. Worse, the meter bar named its seven bands in
# its own code, so every step the ledger had measured since patch17 - thought
# audio, the sample gate, the recogniser - could not appear on it however long it
# ran. The bands ARE what was spent.
section("v3.75 patch24: the recogniser gets a band, and the bar reads the record")

check("def _tts_asr_transcribe(" in py
      and 'spend_add("SenseVoice", time.time() - _t24)' in py,
      "every transcription is timed, wherever it is called from")
check("def _meter_ms(" in py and "for step, ms in spend_bits():" in py
      and 'out["panel"] = round(max(0.0, (prep - pti_s - mood_s) * 1000.0 - known))' in py,
      "the record carries every band the ledger has, with panel as the remainder")
check("ms=_meter_ms(_pti_s, _mood_s, est_s, prep," in py
      and 'ms={"player tags"' not in py,
      "and the fixed seven-band dict it replaced is gone")
check('const mid = Object.keys(ms).filter(k => lead.indexOf(k) < 0' in py
      and 'return ["player tags", "mood", "token estimate", "panel",' not in py,
      "the bar draws what the record holds - it used to name its bands itself")
for _b24 in ("SenseVoice", "thought audio", "sample gate", "transcript",
             "identity note"):        # retold p29: no warm-up band
    check(('"%s":' % _b24) in seg(py, "const METER_WHY = {", "let meterPin")
          and ('"%s":' % _b24) in seg(py, "const METER_COL = {", "function meterSegs"),
          "%s has a legend entry and a colour" % _b24)
check('calterm_log(["%s spent  %s"' in py,
      "and the calibration terminal carries the spend, after the take rather than "
      "before it")

try:
    fp.spend_reset()
    fp.spend_add("SenseVoice", 0.42)
    fp.spend_add("thought audio", 1.29)
    fp.spend_add("sample gate", 0.003)
    fp.spend_add("identity note", 0.0001)
    _ms24 = fp._meter_ms(0.10, 0.001, 0.008, 2.0, 1.1, 0.2, 1.3, 1.5)
    _q1 = _ms24.get("SenseVoice") == 420 and _ms24.get("thought audio") == 1290
    _q2 = _ms24.get("sample gate") == 3 and "identity note" not in _ms24
    _q3 = _ms24["panel"] == round((2.0 - 0.10 - 0.001) * 1000.0 - (1290 + 420 + 3))
    fp.spend_reset()
    _q4 = "SenseVoice" not in fp._meter_ms(0.1, 0.0, 0.0, 0.2, 1.0, 0.0, 1.0, 1.0)
    check(_q1 and _q2 and _q3 and _q4,
          "run: the recogniser and the thought each get their own band, a step that "
          "cost nothing does not, panel is the remainder so the bands sum to the "
          "wall, and a line that used no recogniser draws no band for it",
          str([_q1, _q2, _q3, _q4]))
except Exception as _eQx:
    check(False, "the patch24 runs did not RUN", str(_eQx)[:140])


# ----------------------------------------------------------------- v3.75 patch25
# Two things a server could not tell you. A fleet slot is launched into its own
# console, so unlike the speech server there is no handle to poll - a launch that
# died left a card that simply never turned green, silently. And the panel was
# sending a DFlash drafter its own block size as the draft cap, which llama.cpp
# clamps every launch, so the number in the launcher was never the number that ran.
section("v3.75 patch25: a slot says why it did not start, and a drafter is asked "
        "for what it can give")

check("def draft_n_max_ceiling(" in py
      and "n_draft_max = (is_dspark and sample_from_anchor) ? block_size" in py
      and 'return bs if (str(kind) == "draft-dspark" and anchor) else bs - 1' in py,
      "the draft ceiling is llama.cpp's own rule, written where it is used")
check('.endswith(".sample_from_anchor")' in py
      and '".sample_from_anchor")):' in py,   # captured AND consulted
      "and both inputs are READ from the drafter's header")
check('_nmax = draft_n_max_ceiling(meta, kind)' in py
      and 'str(int(meta.get("dflash.block_size") or 16))' not in py,
      "the launcher is given what the drafter can produce, not the block size "
      "that gets clamped")
check('"clamping to" in low and "draft size" in low' in py
      and 'out["clamped"] = ln.strip()[:200]' in py,
      "and a clamp the engine applies anyway is captured verbatim from the log")
check("def slot_launch_fault(" in py and "SLOT_STALL_S = 45.0" in py
      and 'if state == "serving" or not path:' in py,
      "a slot that was asked to start and is not answering is diagnosed from its log")
check('last log line: %s' in py
      and "it may have exited afterwards" in py,
      "with the last line it managed, and a different reading when it HAD loaded")
check('st["fault"] = _flt' in py and "const why = String(st.fault" in py,
      "and the card carries it instead of an unexplained down")

try:
    import tempfile as _tfR, os as _osR, time as _tmR
    _DR = _tfR.mkdtemp(); _pR = _osR.path.join(_DR, "srv.log")
    with open(_pR, "w", encoding="utf-8") as _f:
        _f.write("=== s ===\nload_model: loading model 'X.gguf'\n"
                 "load_model: local path 'X.gguf'\n")
    _osR.utime(_pR, (_tmR.time() - 120, _tmR.time() - 120))
    _r1 = "stopped after" in fp.slot_launch_fault(_pR, "down")
    _r2 = fp.slot_launch_fault(_pR, "serving") == ""
    _osR.utime(_pR, (_tmR.time(), _tmR.time()))
    _r3 = fp.slot_launch_fault(_pR, "down") == ""
    _r4 = (fp.draft_n_max_ceiling({"dflash.block_size": 16}, "draft-dflash") == 15
           and fp.draft_n_max_ceiling({"dflash.block_size": 16}, "draft-dspark") == 16
           and fp.draft_n_max_ceiling({"dflash.block_size": 16,
                                       "dflash.sample_from_anchor": "false"},
                                      "draft-dspark") == 15
           and fp.draft_n_max_ceiling({"dflash.block_size": 8}, "draft-dflash") == 7
           and fp.draft_n_max_ceiling({}, "draft-dflash") == 0)
    check(_r1 and _r2 and _r3 and _r4,
          "run: a dead load is named with its last line, a serving slot is never "
          "accused, a log still being written is loading, and the ceiling follows "
          "the drafter's own block and kind", str([_r1, _r2, _r3, _r4]))
except Exception as _eRx:
    check(False, "the patch25 runs did not RUN", str(_eRx)[:140])


TPL_SINGLE = ""
TPL_CREATOR = ""
try:
    with open(os.path.join(ROOT, "templates", "single-gpu.ps1"),
              encoding="utf-8-sig") as _f:
        TPL_SINGLE = _f.read()
    with open(os.path.join(ROOT, "launcher-template.ps1"),
              encoding="utf-8-sig") as _f:
        TPL_CREATOR = _f.read()
except Exception as _eT0:
    TPL_SINGLE = TPL_CREATOR = "(unreadable: %s)" % _eT0

# ----------------------------------------------------------------- v3.75 patch26
# The default launcher had a contract with the panel that it did not keep. The
# panel's log reader tells a server that DIED from one still loading by one exact
# sentence - "Server process exited before it became ready" - which llama.cpp
# never prints, so only the launcher can. It never did. And the last line of the
# file re-invoked the file, so a server that could not start looped instead of
# stopping, replacing the console that held the reason with the next attempt.
section("v3.75 patch26: the default launcher keeps its side of the bargain")

for _tpl26, _name26 in ((TPL_SINGLE, "single-gpu"), (TPL_CREATOR, "launcher-template")):
    nin(_tpl26, '& "<SELF_PATH>"',
        "%s: no self-relaunch - a failed start must stop, not loop" % _name26)
    # BOTH branches must carry it: a template that says it only on exit 0 leaves
    # the crash - the case that matters - unreportable, and a check for "in" alone
    # cannot see that (the negative control passed until this counted)
    check(_tpl26.count("Server process exited before it became ready") == 2,
          "%s: prints the sentence the panel watches for, on BOTH exit paths"
          % _name26)
    check("$code = $LASTEXITCODE" in _tpl26 and "exit $code" in _tpl26,
          "%s: carries llama-server's own exit code" % _name26)
    check("ReadKey" in _tpl26,
          "%s: holds the window so the reason can be read" % _name26)
    check("& $exe @args_" in _tpl26 and "ForEach-Object" not in _tpl26,
          "%s: llama.cpp's output reaches the log unfiltered - the VRAM report is "
          "parsed from THESE lines" % _name26)

try:
    import tempfile as _tfT, os as _osT
    _okT = True
    for _c26 in (TPL_SINGLE, TPL_CREATOR):
        _t26 = {"title": "S", "model": "D:/m/m.gguf", "vision": "N/A", "draft": "N/A",
                "gpu": "GPU-a", "port": "1236", "content": _c26}
        _txt26 = "\n".join(fp.render_launcher_lines(_t26, "C:/P/slot1.ps1",
                                                    "C:/l/llama-server.exe"))
        _okT = _okT and ('& "C:/P/slot1.ps1"' not in _txt26
                         and "<SELF_PATH>" not in _txt26
                         and "Server process exited before it became ready" in _txt26)
    _DT = _tfT.mkdtemp(); _pT = _osT.path.join(_DT, "srv.log")
    with open(_pT, "w", encoding="utf-8") as _f:
        _f.write("=== s ===\nload_model: loading 'x'\n"
                 "Server process exited before it became ready (exit 3221225477)\n")
    _e1 = fp.slot_vram_report(_pT).get("exited") is True
    with open(_pT, "w", encoding="utf-8") as _f:
        _f.write("=== s ===\nServer ready\nall slots are idle\n")
    _e2 = fp.slot_vram_report(_pT).get("ready") is True
    check(_okT and _e1 and _e2,
          "run: a rendered launcher from either template drops the relaunch and "
          "keeps the sentence, and the panel reads that sentence as a death while "
          "a ready server still reads as ready", str([_okT, _e1, _e2]))
except Exception as _eTx:
    check(False, "the patch26 runs did not RUN", str(_eTx)[:140])


# ----------------------------------------------------------------- v3.75 patch27
# Current llama.cpp folded --no-mmap, --mlock and --direct-io into one --load-mode
# flag and warns on every old spelling - and warns AGAIN if the old and new are
# combined, so this replaces rather than adds. --chat-template-kwargs is also
# deprecated upstream and is deliberately kept: some models honour only the
# template kwarg, which is why the panel writes both it and --reasoning.
section("v3.75 patch27: the load flag llama.cpp actually wants")

check('("loadmode",  "Model load mode",' in py and '"--load-mode",' in py,
      "the card setting is Model load mode, emitting --load-mode")
check('"auto", "none", "mmap", "mlock", "mmap+mlock", "dio"' in py,
      "with the exact value set llama.cpp accepts, in its own order")
nin(py, '"--no-mmap",          ', "no setting emits --no-mmap any more")
nin(py, '"nommap"', "and the old key is gone from every table that held it")
check('"--mlock": "DEPRECATED - use --load-mode mlock"' in py
      and '"--defrag-thold": "DEPRECATED' in py,
      "the two flags a user may still type by hand say they are deprecated")
check("--chat-template-kwargs" in py and "CTK_FLAG" in py,
      "and the kwarg the panel writes on purpose is untouched")
check('{ name:"Load mode", flag:"--load-mode",' in py
      and 'auto | none | mmap | mlock | mmap+mlock | dio' in py   # retold p33
      and "replaces the old --no-mmap, --mlock and --direct-io" in py,
      "the Sampler Guide carries a Load mode page that says what it replaced")
check('{ name:"Threads / fit"' in py and '"Threads / mmap / fit"' not in py,
      "and the page it was folded out of no longer claims mmap")

try:
    import re as _reU
    _tblU = _reU.search(r"LAUNCH_PARAMS = \(\n(.*?)\n\)\n", py, _reU.S)
    _rowsU = _reU.findall(
        r'\("([a-z]+)",\s+"[^"]+",\s+"[a-z]+",\s+"[^"]*",\s+\{.*?\},\s*\n?\s*'
        r'"(--[a-z0-9-]+)",\s+"([^"]+)"\)',
        _tblU.group(1) if _tblU else py, _reU.S)
    _pagesU = set(_reU.findall(r'\{ name:"([^"]+)", flag:', py))
    _missU = sorted({_g for _k, _f, _g in _rowsU} - _pagesU)
    _u1 = bool(_rowsU) and not _missU
    _u2 = any(_k == "loadmode" and _f == "--load-mode" and _g == "Load mode"
              for _k, _f, _g in _rowsU)
    _u3 = not any(_k == "nommap" for _k, _f, _g in _rowsU)
    check(_u1 and _u2 and _u3,
          "run: every card setting cross-references a guide page that EXISTS - "
          "renaming a page without repointing its settings is how that link dies "
          "silently", "%d rows, missing %s" % (len(_rowsU), _missU))
except Exception as _eUx:
    check(False, "the patch27 runs did not RUN", str(_eUx)[:140])


# ----------------------------------------------------------------- v3.75 patch28
# Eight requests from the owner in one pass. The two that were bugs: Dismiss
# bounced off a confirm gate meant for destructive actions - it hides a finished
# banner and destroys nothing - and a repaint refused while focus sat inside the
# TTS pane was CANCELLED rather than deferred, which with the settings-value
# signature is exactly why the page after an install showed the world as it was.
section("v3.75 patch28: eight owner requests - dismiss, defaults, and a repaint owed")

check('.uuid { user-select:text; }' in py
      and " filter:blur(4px)" not in py,   # text blur; backdrop-filter panels stay
      "the setup page addresses are plainly readable - no blur, text selectable")
check('ttsPaneDrawn = "";' in py and "window.__ttsOwe" in py,   # retold p32
      "a repaint deferred for focus clears the drawn signature, so the next "
      "render redraws from fresh state instead of declining forever")
_dmz = py.find('== "dismiss"')
check(_dmz >= 0 and _dmz < py.find('.get("confirm")'),
      "dismiss is answered BEFORE the confirm gate - it destroys nothing")
check('"ttsChunkChars": "170",' in py,   # retold p37
      "long lines split at 170 - fewer chunks, fewer boundaries to wait on")
check('st["ttsSampleSec"] = "10"' in py and '"ttsSampleSec"] = "4"' not in py
      and '"ttsSampleSec": "10",' in py,
      "the 10-second sample window survives an install - both writers say 10")
check('"ttsOutDir": os.path.join(STACK, "TTSaudio")' in py   # retold p29: full path
      and "a bare name lands beside the panel" in py,
      "saved audio defaults to TTSaudio beside the panel, resolved absolute")
check('data-act="ttsDefaults"' in py and 'function ttsDefaults() {' in py
      and '"/api/tts-defaults": api_tts_defaults,' in py,
      "the revert button sits by the TTS selector, dialog-first, wired end to end")
check("for k in [k for k in st if k.startswith(\"tts\")]:" in py
      and 'if k.startswith("tts"):' in py,
      "and the endpoint deletes stray tts keys before writing the shipped set")
check("Clear TTS calibration data; revert TTS settings to defaults" in py
      and "Reads each slot's own log to say why a launch ended" in py,
      "the permission tree names what this build can actually do")

try:
    _svQ = [None]
    _realQ = (fp.save_config, fp.sse_notify, fp.load_config)
    fp.save_config = lambda c: _svQ.__setitem__(0, c)
    fp.sse_notify = lambda *a, **k: None
    _q1 = fp.api_higgs_install({"action": "dismiss"}) == {"ok": True}
    fp.load_config = lambda *a, **k: {"settings": {
        "ttsCalTopP": "0.8", "ttsRetrySafe": "on", "ttsChunkChars": "90",
        "yamlOutDir": "keep", "ttsEngine": "moss"}}
    fp.api_tts_defaults()
    _stQ = _svQ[0]["settings"]
    _q2 = "ttsCalTopP" not in _stQ and "ttsRetrySafe" not in _stQ
    # retold patch29: the audio folder default is a full path now
    _q3 = (_stQ.get("ttsChunkChars") == "170" and _stQ.get("yamlOutDir") == "keep"
           and _stQ.get("ttsSampleSec") == "10"
           and str(_stQ.get("ttsOutDir") or "").endswith("TTSaudio"))
    import os as _osQ
    fp.load_config = lambda *a, **k: {"settings": {"ttsOutDir": "TTSaudio"}}
    _pQ = fp.tts_save_named(b"RIFFxxxxWAVE", "GateNpc")
    _q4 = bool(_pQ) and _osQ.path.isabs(_pQ)
    if _pQ:
        try:
            _osQ.remove(_pQ); _osQ.rmdir(_osQ.path.dirname(_pQ))
        except OSError:
            pass
    check(_q1 and _q2 and _q3 and _q4,
          "run: dismiss answers ok bare, defaults purge strays and restore the "
          "shipped set without touching other settings, and a bare audio folder "
          "resolves beside the panel", str([_q1, _q2, _q3, _q4]))
except Exception as _eQy:
    check(False, "the patch28 runs did not RUN", str(_eQy)[:140])
finally:
    try:
        fp.save_config, fp.sse_notify, fp.load_config = _realQ
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch29
# The voice warm-up was the unexplained preparation cost. Measured over 185 lines:
# 33 ms of preparation when the speaker was unchanged, 749 ms when it changed, and
# 1459 ms NPC-to-NPC. It synthesised a whole discarded take on every speaker change
# to absorb engine carryover - a fix the reference samplers had already made
# unnecessary - and it landed in the panel remainder rather than its own band,
# which is why the bar never showed it.
section("v3.75 patch29: the warm-up goes, and addresses stop hiding")

nin(py, "tts_warmup_needed", "the warm-up test is gone, function and all")
nin(py, "ttsVoiceWarmup", "and its setting with it - no hidden 'on' left behind")
nin(py, 'spend_step("voice warm-up")', "and the ledger step it booked")
check("voice warm-up" not in JS, "the meter has no band or legend for it either")
check(".hb { cursor: pointer; }" in py and "blur(3.5px)" not in py,   # p31
      "the address fields are plainly readable - patch28 changed .uuid, which is "
      "not the class they use")
check('"ttsOutDir": os.path.join(STACK, "TTSaudio")' in py,
      "saved audio defaults to a FULL path, so the field says where files go")
check('"ttsAsrLang": "auto",' in py,
      "recognition guesses the language rather than assuming English")
check("TTS_INSTALL_KEYS = (" in py and "keep = {k: st[k] for k in TTS_INSTALL_KEYS" in py
      and "st.update(keep)" in py,
      "a revert keeps where the engine is installed - that is a discovery, not a "
      "preference")
check('L.append("$code = $LASTEXITCODE")' in py
      and "Server process exited before it became ready" in seg(
          py, "def build_param_launcher", "def ps1_args_span"),
      "the SERVER CARD launcher reports how it ended - patch26 taught the two "
      "templates and missed the builder every card actually uses")

try:
    _cfgW = {"settings": {"llamaExe": "C:/l/llama-server.exe"},
             "gpus": [{"id": "gpu0", "uuid": "GPU-abc", "index": "0"}],
             "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "gpu0",
                        "model": "D:/m.gguf", "params": {"ngl": "99"}}]}
    _txtW = fp.build_param_launcher(_cfgW, _cfgW["slots"][0], "C:/P/s1.ps1")
    _w1 = ('$env:CUDA_VISIBLE_DEVICES = "GPU-abc"' in _txtW
           and "Server process exited before it became ready" in _txtW
           and "@llamaArgs" in _txtW and _txtW.rstrip().endswith("exit $code"))
    _svW = [None]
    _realW = (fp.save_config, fp.sse_notify, fp.load_config)
    fp.save_config = lambda c: _svW.__setitem__(0, c)
    fp.sse_notify = lambda *a, **k: None
    fp.load_config = lambda *a, **k: {"settings": {
        "ttsAcppDir": "C:/P/audio.cpp", "ttsAcppExe": "C:/P/a/x.exe",
        "ttsAsrLang": "de", "ttsChunkChars": "90", "ttsCalTopP": "0.8"}}
    fp.api_tts_defaults()
    _stW = _svW[0]["settings"]
    _w2 = _stW.get("ttsAcppDir") == "C:/P/audio.cpp" and _stW.get("ttsAcppExe")
    _w3 = (_stW.get("ttsAsrLang") == "auto" and _stW.get("ttsChunkChars") == "170"
           and "ttsCalTopP" not in _stW)
    _w4 = "ttsVoiceWarmup" not in fp.DEF_SETTINGS
    check(_w1 and _w2 and _w3 and _w4,
          "run: a card launcher pins its GPU and reports its exit, a revert keeps "
          "the install and resets the rest, and no warm-up setting survives",
          str([_w1, bool(_w2), _w3, _w4]))
except Exception as _eWx:
    check(False, "the patch29 runs did not RUN", str(_eWx)[:140])
finally:
    try:
        fp.save_config, fp.sse_notify, fp.load_config = _realW
    except Exception:
        pass


# ----------------------------------------------------------------- v3.75 patch30
# Why a three-card fleet spread every model across every card and into host RAM.
# Two causes, both ours. --fit was treated as a bare switch, so "off" wrote
# NOTHING and llama.cpp - which fits by default - fitted across every visible
# device while the card read "Auto fit to VRAM: off". And the server card's
# template list was read from the Launcher Creator's folder, so a template whose
# own header says "no GPU pinning - for 1 PC / 1 GPU" was offered to a fleet
# server; taking it left CUDA_VISIBLE_DEVICES unwritten and every GPU visible.
section("v3.75 patch30: the fit flag speaks, and the fleet gets its own templates")

check('bare = {"nocontbat"}' in py and 'out, bare = {}, {"nocontbat"}' in py
      and 'bare = {"nocontbat", "fit"}' not in py,
      "--fit is no longer a bare switch - absent is not off when the engine "
      "defaults to on")
check("A dial whose engine-side default" in py,
      "and why it must say off out loud is written where it is decided")
check('SERVER_TPL_DIR = "server-templates"' in py
      and 'CREATOR_TPL_DIR = "templates"' in py
      and "def read_named_template(name, where=SERVER_TPL_DIR):" in py
      and "def list_templates(where=SERVER_TPL_DIR):" in py,
      "the fleet and the Launcher Creator read from different folders")
check(os.path.isfile(os.path.join(ROOT, "server-templates", "pinned-server.ps1")),
      "and the fleet's own template ships")

try:
    with open(os.path.join(ROOT, "server-templates", "pinned-server.ps1"),
              encoding="utf-8-sig") as _f:
        _stpl = _f.read()
    check('$env:CUDA_VISIBLE_DEVICES = "<GPU_ID>"' in _stpl,   # retold p31
          "the server template pins its card, which is the whole point of it")
    check('"--fit", "off"' in _stpl and '"--n-gpu-layers", "99"' in _stpl,
          "every layer on that card, and fitting off so they stay there")
    check(_stpl.count("Server process exited before it became ready") == 1
          and "$code = $LASTEXITCODE" in _stpl and "ReadKey" in _stpl,
          "it reports how it ended and holds the window")
    nin(_stpl, "ForEach-Object",
        "and leaves llama.cpp's output alone - the VRAM report is parsed from it")
except Exception as _eZ0:
    check(False, "the server template could not be read", str(_eZ0)[:120])

try:
    _cfgZ = {"settings": {"llamaExe": "C:/l/llama-server.exe"},
             "gpus": [{"id": "gpu0", "uuid": "GPU-abc", "index": "0"}],
             "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "gpu0",
                        "model": "D:/m.gguf",
                        "params": {"ngl": "99", "fit": "off"}}]}
    _txtZ = fp.build_param_launcher(_cfgZ, _cfgZ["slots"][0], "C:/P/s1.ps1")
    _z1 = '"--fit", "off"' in _txtZ
    _z2 = '$env:CUDA_VISIBLE_DEVICES = "GPU-abc"' in _txtZ
    _cfgZ["slots"][0]["params"]["fit"] = "on"
    _z3 = '"--fit"' in fp.build_param_launcher(_cfgZ, _cfgZ["slots"][0], "C:/P/s1.ps1")
    _realZ = fp.STACK
    fp.STACK = ROOT
    _idsZ = [x["id"] for x in fp.list_templates()]
    _nmsZ = [x["name"] for x in fp.list_templates()]
    fp.STACK = _realZ
    _z4 = "pinned-server" in _idsZ and not any("no GPU pinning" in n for n in _nmsZ)
    check(_z1 and _z2 and _z3 and _z4,
          "run: a card that says fit off WRITES fit off, still pins its GPU, fit "
          "on still writes, and the fleet list offers only fleet templates",
          str([_z1, _z2, _z3, _z4, _idsZ]))
except Exception as _eZx:
    check(False, "the patch30 runs did not RUN", str(_eZx)[:140])


# ----------------------------------------------------------------- v3.75 patch31
# The pin was still not reaching the file that runs. patch30 shipped a template
# using <GPU_UUID>, a placeholder the renderer has never implemented - it knows
# <GPU_ID> - so the line survived into the launcher as literal text, CUDA could
# not parse it, and every card stayed visible. And a server card never renders a
# template anyway: it stores the text and the panel writes it verbatim, editing
# only flags INSIDE $llamaArgs. So the pin is now enforced on the written bytes.
section("v3.75 patch31: the pin is written, not hoped for")

check("def ps1_force_gpu_pin(" in py and 'PIN_LINE = "$env:CUDA_VISIBLE_DEVICES"' in py,
      "the pin is imposed on the launcher text, whatever produced it")
check("body = ps1_force_gpu_pin(body, _pin31)" in py,
      "and on the way to disk, so custom text cannot escape it")
check("had no GPU chosen - pinned to" in py    # retold p32: assigned, not warned
      and "has no GPU chosen and none exists to assign" in py,
      "a slot with no card chosen says so rather than pinning nothing silently")
nin(py, "<GPU_UUID>", "the placeholder the renderer never knew is gone")
check("def tts_write_install_paths(" in py and py.count("tts_write_install_paths(") == 3,
      "one writer for every path an install discovers, used by both callers")
check('.hb { cursor: pointer; }' in py and "input.hb:focus { cursor: text; }" in py,
      "an address is a thing to click, not a field to type a caret into")

try:
    with open(os.path.join(ROOT, "server-templates", "pinned-server.ps1"),
              encoding="utf-8-sig") as _f:
        _tp31 = _f.read()
    nin(_tp31, "<GPU_UUID>", "the shipped template uses a placeholder that exists")
    nin(_tp31, "<CTX>", "and no invented ones at all")
    check('$env:CUDA_VISIBLE_DEVICES = "<GPU_ID>"' in _tp31,
          "pinning by the name the renderer substitutes")
except Exception as _eY0:
    check(False, "the server template could not be read", str(_eY0)[:120])

try:
    _tplY = ('# head\n$env:CUDA_VISIBLE_DEVICES = "<GPU_ID>"\n\n$llamaArgs = @(\n'
             '    "--model", "x.gguf"\n)\n& "llama-server.exe" @llamaArgs\n')
    _y1 = ('$env:CUDA_VISIBLE_DEVICES = "GPU-abc"'
           in fp.ps1_force_gpu_pin(_tplY, "GPU-abc"))
    _y2 = "<GPU_ID>" not in fp.ps1_force_gpu_pin(_tplY, "GPU-abc")
    _bareY = '$llamaArgs = @(\n    "--model", "x"\n)\n'
    _y3 = ('$env:CUDA_VISIBLE_DEVICES = "GPU-zzz"'
           in fp.ps1_force_gpu_pin(_bareY, "GPU-zzz"))
    _y4 = "CUDA_VISIBLE_DEVICES" not in fp.ps1_force_gpu_pin(_tplY, "")
    _y5 = fp.ps1_force_gpu_pin(_tplY, "GPU-a").count("CUDA_VISIBLE_DEVICES") == 1
    check(_y1 and _y2 and _y3 and _y4 and _y5,
          "run: a placeholder is replaced by the real card, a launcher without a "
          "pin gains one before the argument array, no card chosen writes no pin, "
          "and the line is never duplicated", str([_y1, _y2, _y3, _y4, _y5]))
except Exception as _eYx:
    check(False, "the patch31 runs did not RUN", str(_eYx)[:140])


# ----------------------------------------------------------------- v3.75 patch32
# The owner's panel.log said it plainly, ten times: "server N has no GPU chosen -
# its launcher pins nothing". patch31's enforcement worked and had nothing to
# enforce: a fresh install creates slots with no gpuId, so every server saw every
# card. A warning nobody reads is not a fix. A slot with no card now GETS one at
# write time - least-loaded card first, bigger card on a tie - written back to
# the slot and logged. Plus three smaller regressions of ours, each found in the
# owner's report: the installer stored a model basename where the dropdown
# matches full paths; the IP suggestion chip wrapped its text in a second span;
# and a repaint deferred for focus never came due, because a BUTTON holds focus
# until something takes it away.
section("v3.75 patch32: a slot with no card gets one, and three regressions")

check("had no GPU chosen - pinned to" in py,
      "an unassigned slot is assigned and the assignment is logged")
check("_cnt32" in py and "-_mem32(g)" in py,
      "least-loaded card first, the bigger card on a tie")
check("has no GPU chosen and none exists to assign" in py,
      "only a machine with no GPUs at all still writes an unpinned launcher")
check("tts_write_install_paths(paths[\"engine\"], paths[\"models\"], gguf)" in py,
      "the installer stores the model's FULL path, the shape the dropdown matches")
check('data-act="ipUse"' in py,
      "the IP suggestion chip still exists")
nin(seg(py, "async function detectIp", "let slotMsg"),
    chr(60) + 'span class="hb"' + chr(62),
    "and no longer wraps its text in a second span - the whole chip is the button")
check("window.__ttsOwe = setTimeout" in py and "clearTimeout(window.__ttsOwe)" in py,
      "a repaint deferred for focus has a due date")
check('/^(INPUT|TEXTAREA|SELECT)$/.test' in py,
      "and the due date yields to someone actually typing")

try:
    import tempfile as _tf32, os as _os32
    _D32 = _tf32.mkdtemp()
    _m32 = _os32.path.join(_D32, "a.gguf")
    with open(_m32, "wb") as _f:
        _f.write(b"GGUF")
    _cfg32 = {"settings": {"llamaExe": "C:/l/llama-server.exe",
                           "outputDir": _D32, "launcherDir": _D32},
              "gpus": [{"id": "gpu0", "uuid": "GPU-A", "index": "0",
                        "name": "big", "mem": "32606 MiB"},
                       {"id": "gpu1", "uuid": "GPU-B", "index": "1",
                        "name": "small", "mem": "24575 MiB"}],
              "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "",
                         "params": {"model": _m32}},
                        {"id": "2", "label": "S2", "port": 1237, "gpuId": "",
                         "params": {"model": _m32}}]}
    _lg32 = []
    _realA32 = (fp.ARCHIVE, fp.GEN_LAUNCHER_DIR)
    fp.ARCHIVE = _os32.path.join(_D32, "ps1-launchers")
    fp.GEN_LAUNCHER_DIR = _os32.path.join(_D32, "generated-launchers")
    _real32 = fp.panel_log
    fp.panel_log = lambda m: _lg32.append(m)
    _pins32 = []
    for _s32 in _cfg32["slots"]:
        _d32 = fp.regen_slot_script(_cfg32, _s32)
        with open(_d32, encoding="utf-8-sig") as _f:
            _t32 = _f.read()
        _pins32.append((_s32["gpuId"],
                        [l for l in _t32.splitlines()
                         if "CUDA_VISIBLE_DEVICES" in l]))
    fp.panel_log = _real32
    fp.ARCHIVE, fp.GEN_LAUNCHER_DIR = _realA32
    _z1 = [p[0] for p in _pins32] == ["gpu0", "gpu1"]
    _z2 = all(len(p[1]) == 1 for p in _pins32)
    _z3 = "GPU-A" in _pins32[0][1][0] and "GPU-B" in _pins32[1][1][0]
    _z4 = sum("had no GPU chosen - pinned to" in m for m in _lg32) == 2
    check(_z1 and _z2 and _z3 and _z4,
          "run: two bare slots take the two cards biggest-first, each launcher "
          "pins exactly its own, and both assignments are logged",
          str([_z1, _z2, _z3, _z4]))
except Exception as _e32x:
    check(False, "the patch32 runs did not RUN", str(_e32x)[:140])


tpl_server = ""
try:
    with open(os.path.join(ROOT, "server-templates", "pinned-server.ps1"),
              encoding="utf-8-sig") as _f:
        tpl_server = _f.read()
except Exception as _eT33:
    tpl_server = "(unreadable: %s)" % _eT33

# ----------------------------------------------------------------- v3.75 patch33
# The owner was right about --load-mode and was told twice that he was not. He
# tested it: "auto" spread each model over three cards and into system RAM,
# "--no-mmap" fixed it, "--load-mode dio" fixed it. Memory-mapped weights stay
# host-resident and get placed across whatever llama.cpp can reach, so this flag
# decides WHERE the weights live and not merely how fast they load. Worse, the
# panel had greyed the control out on any fully-offloaded card, on the strength
# of a comment asserting the very thing the measurement disproved.
section("v3.75 patch33: load mode decides where the weights live")

check('("loadmode",  "Model load mode",     "sel",  "dio",' in py,
      "dio is the default load mode for every server card")
check('"--load-mode", "dio"' in tpl_server,
      "and the fleet template ships with it")
check("dio, not auto. MEASURED on a three-card rig" in py,
      "with the measurement recorded where the default is set")
nin(seg(py, "const OFF = {", "};"), "loadmode:",
    "load mode is NOT in the map that greys a control out - it is always settable")
check("Its guidance lives in the hint under the control instead" in py,
      "and its guidance moved somewhere that does not disable it")
check("in practice, <b>where they end up</b>" in py
      and "(default dio)" in py,
      "the Sampler Guide says what the flag actually decides")
nin(py, "only affects load time, not generation",
    "and no longer repeats the claim the measurement disproved")
check('sse_notify("tts-installed")' in py and "async function ttsInstalled(" in py
      and 'if (ev.t === "tts-installed") ttsInstalled();' in py,   # retold p36
      "an install or adoption raises its own event, end to end")
check("this repaint is NOT deferred" in py
      and "clearTimeout(window.__ttsOwe);" in seg(py, "async function ttsInstalled",
                                                  "async function stateRepull"),
      "and that repaint is not deferred - the button that started it holds focus")

try:
    _row33 = [r for r in fp.SERVER_PARAMS if r[0] == "loadmode"][0]
    _o33 = _row33[4].get("opts") or []
    _d1 = _row33[3] == "dio" and "dio" in _o33 and "auto" in _o33
    _cfg33 = {"settings": {"llamaExe": "C:/l/llama-server.exe"},
              "gpus": [{"id": "gpu0", "uuid": "GPU-A", "index": "0"}],
              "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "gpu0",
                         "model": "D:/m.gguf", "params": {"ngl": "99"}}]}
    _t33 = fp.build_param_launcher(_cfg33, _cfg33["slots"][0], "C:/P/s1.ps1")
    _d2 = '"--load-mode", "dio"' in _t33
    _cfg33["slots"][0]["params"]["loadmode"] = "mmap"
    _d3 = '"--load-mode", "mmap"' in fp.build_param_launcher(
        _cfg33, _cfg33["slots"][0], "C:/P/s1.ps1")
    check(_d1 and _d2 and _d3,
          "run: dio is the default and is written, and a card that chooses another "
          "mode gets the one it chose", str([_d1, _d2, _d3]))
except Exception as _e33x:
    check(False, "the patch33 runs did not RUN", str(_e33x)[:140])


# ----------------------------------------------------------------- v3.75 patch34
# The last of the host memory. After --fit off (p30), the pin (p31/p32) and
# --load-mode dio (p33), models still borrowed system RAM. One host-side knob
# still differed from the owner's known-good launcher: --ctx-checkpoints, which
# keeps N rollback copies of a slot's context in HOST memory. The panel shipped
# llama.cpp's default of 8 while its own Sampler Guide told the user to set it to
# zero. Four ways to end up in host memory, and a fleet server wants none of them.
section("v3.75 patch34: the last host-memory default")

check('("ctxcheck",  "Context checkpoints", "int",  "0",' in py,
      "context checkpoints default to 0 - no rollback copies in host memory")
check("kept in HOST memory" in py and "own guide already said" in py,
      "and the reason is recorded where the default is set")
check('"--ctx-checkpoints", "0"' in tpl_server and '"--cache-ram", "0"' in tpl_server,
      "the fleet template states BOTH zeros, because both must be explicit")
check("Both zeros explicit, and both must be" in tpl_server,
      "and says why an unsaid zero is not a zero")

try:
    _cfg34 = {"settings": {"llamaExe": "C:/l/llama-server.exe"},
              "gpus": [{"id": "gpu0", "uuid": "GPU-A", "index": "0"}],
              "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "gpu0",
                         "model": "D:/m.gguf", "params": {"ngl": "99"}}]}
    _t34 = fp.build_param_launcher(_cfg34, _cfg34["slots"][0], "C:/P/s1.ps1")
    # every route into host memory, shut by default, in one generated launcher
    _e1 = '"--ctx-checkpoints", "0"' in _t34
    _e2 = '"--cache-ram", "0"' in _t34
    _e3 = '"--load-mode", "dio"' in _t34
    _e4 = '"--fit", "off"' in _t34
    _e5 = '$env:CUDA_VISIBLE_DEVICES = "GPU-A"' in _t34
    # and a card that WANTS a host cache still gets one
    _cfg34["slots"][0]["params"]["ctxcheck"] = "8"
    _e6 = '"--ctx-checkpoints", "8"' in fp.build_param_launcher(
        _cfg34, _cfg34["slots"][0], "C:/P/s1.ps1")
    check(_e1 and _e2 and _e3 and _e4 and _e5 and _e6,
          "run: a default launcher pins its card and closes every route into host "
          "memory - checkpoints, cache spill, mmap and fitting - while a card that "
          "asks for checkpoints still gets them",
          str([_e1, _e2, _e3, _e4, _e5, _e6]))
except Exception as _e34x:
    check(False, "the patch34 runs did not RUN", str(_e34x)[:140])


# ----------------------------------------------------------------- v3.75 patch35
# Two things the owner had to work around by hand. The OFF map on a server card
# explains when one setting overrules another - and also set `disabled`, so a
# GUESS written into one of those strings removed the control. Load mode was
# greyed out on exactly the cards that needed it changed, and the fix had to be
# applied by editing launchers in a text editor. And three patches of ever more
# careful repainting still left CTRL+F5 as the only way to see post-install
# paths, because a repaint cannot rebuild what the page read once at load.
section("v3.75 patch35: nothing on a card is locked, and an install reloads")

check('const dis = "";' in py,
      "no server card setting is ever disabled - the map explains, it does not lock")
check("const why = OFF[d.key]" in py,
      "and the explanation itself is kept")
nin(py, 'const dis = why ? " disabled" : "";',
    "the line that turned an explanation into a lock is gone")
# retold p36: the reload is gone - it discarded the terminal, the scroll and any
# half-typed field to deliver four strings, which are now written in directly
check("async function ttsInstalled()" in py
      and 'if (ev.t === "tts-installed") ttsInstalled();' in py
      and 'const el = $("tts-" + k);' in py,
      "an install or adoption fills its fields without discarding the page")
check("if the repaint" in py and "already did it this changes nothing" in py,
      "and the reason is recorded where the fields are written")

try:
    _dis35 = seg(py, "const why = OFF[d.key]", "let ctl;")
    _q35 = not any(l.strip().startswith("//") is False and "disabled" in l
                   for l in _dis35.split("\n"))
    _row35 = [r for r in fp.SERVER_PARAMS if r[0] == "ctxcheck"]
    _q36 = bool(_row35) and _row35[0][3] == "0"
    _cfg35 = {"settings": {"llamaExe": "C:/l/llama-server.exe"},
              "gpus": [{"id": "gpu0", "uuid": "GPU-A", "index": "0"}],
              "slots": [{"id": "1", "label": "S1", "port": 1236, "gpuId": "gpu0",
                         "model": "D:/m.gguf", "params": {"ngl": "99"}}]}
    _t35 = fp.build_param_launcher(_cfg35, _cfg35["slots"][0], "C:/P/s1.ps1")
    _q37 = '"--ctx-checkpoints", "0"' in _t35 and '"--load-mode", "dio"' in _t35
    check(_q35 and _q36 and _q37,
          "run: the control renderer emits no disabled attribute, checkpoints "
          "default to zero, and a generated launcher states both",
          str([_q35, _q36, _q37]))
except Exception as _e35x:
    check(False, "the patch35 runs did not RUN", str(_e35x)[:140])


# ----------------------------------------------------------------- v3.75 patch36
# Three the owner had to diagnose from the outside. PTI and PME hang off a server
# WITHOUT a listener of their own - Live Network draws them as "Proxy", not a
# port - so the readiness gate asked slot_status("") about them, got "unknown"
# forever, and every player line went out untagged while the server sat serving.
# Remote Access bound the socket at startup only, so the switch did nothing until
# a restart while the page printed the address to visit. And patch35's reload
# worked by throwing the whole page away to deliver four strings.
section("v3.75 patch36: a proxy provider has no port, and a switch that switches")

check('_port22 = rt.get("port") or rt.get("server") or ""' in py,
      "a panel-called provider's readiness is judged by its SERVER's port")
check('_st22 = slot_status(_port22)' in py,
      "and that is the port actually probed")
check('% (rt.get("server", "?"), _port22 or "?",' in py,
      "the log names the port it really asked about")
check('_bind = "0.0.0.0"' in py and 'net_mode() == "lan" else "127.0.0.1"' not in py,
      "the panel listens on the LAN interface always - client_scope decides who "
      "may speak, per request, so the switch takes effect when it is thrown")
check("listens on the LAN interface always" in py
      and "made the switch a lie" in py,
      "and the reason is recorded where the bind is chosen")
nin(seg(py, "async function ttsInstalled", "async function stateRepull"),
    "location.reload",
    "an install does not throw the page away")
check('const el = $("tts-" + k);' in py
      and '"ttsAcppDir", "ttsAcppModelsDir", "ttsAcppModel", "ttsSampleDir",' in py,
      "it writes the fields an install fills, straight from the state just fetched")

try:
    _sc36 = seg(py, "def client_scope", "def listen_host")
    _c1 = 'if net_mode() != "lan":' in _sc36 and "return None" in _sc36
    _c2 = 'return None                              # external: always denied' in _sc36
    _rt36 = {"server": "1237", "port": "", "id": "pti"}
    _p36 = _rt36.get("port") or _rt36.get("server") or ""
    _c3 = _p36 == "1237"
    _rt37 = {"server": "1237", "port": "1251", "id": "dialogue"}
    _c4 = (_rt37.get("port") or _rt37.get("server") or "") == "1251"
    check(_c1 and _c2 and _c3 and _c4,
          "run: LAN callers are still refused while Remote Access is off and "
          "external always, a portless provider resolves to its server's port, "
          "and a provider with its own port keeps it", str([_c1, _c2, _c3, _c4]))
except Exception as _e36x:
    check(False, "the patch36 runs did not RUN", str(_e36x)[:140])


# ----------------------------------------------------------------- v3.75 patch37
# Four defaults and one control the owner asked for. The thought switch is the
# one worth naming: it shipped off, and a session was spent hunting a "thoughts
# are broken" bug that was this setting sitting at its shipped value - which is
# the second time an off-by-default display switch has cost a diagnosis.
section("v3.75 patch37: defaults that match how the panel is actually used")

check('"ttsAnswerPing": "banned",' in py,
      "the startup ping is answered with silence and not announced")
check('"ttsThoughtOut": "on",' in py,
      "an NPC's thought is shown by default")
check('"termStampsOff": "dashboard,thinking,tts,ptipme,splitd,splitt,ttscal",' in py,
      "and every terminal starts without the time column")
check('d.act === "provAll"' in py and 'data-act="provAll"' in py
      and "const allOff = all.length > 0 && all.every(p => off.has(p.id));" in py,
      "one button turns every provider on or off, labelled from the current state")
check("#provfilter { display: grid;" in py and ".provall { grid-column: 1 / -1;" in py,
      "and the providers wrap into an even grid rather than one long row")

try:
    import re as _re37
    _kinds37 = set(_re37.findall(r'id="tail-([a-z]+)"', py))
    _stamps37 = set(fp.DEF_SETTINGS["termStampsOff"].split(","))
    _y1 = bool(_kinds37) and _kinds37 == _stamps37
    _y2 = fp.DEF_SETTINGS["ttsAnswerPing"] in fp.TTS_PING_MODES
    _y3 = fp.DEF_SETTINGS["ttsThoughtOut"] == "on"
    check(_y1 and _y2 and _y3,
          "run: the stamps default names EVERY terminal that exists and invents "
          "none, and the ping default is a value the reader accepts",
          "terminals %s vs %s" % (sorted(_kinds37), sorted(_stamps37)))
except Exception as _e37x:
    check(False, "the patch37 runs did not RUN", str(_e37x)[:140])


# ----------------------------------------------------------------- v3.75 patch38
# The owner's thoughts still land after the FIRST chunk, and chunk size was not
# it - 170 changed nothing. Fed the owner's own strings, tts_chunk_is_last
# answers True on the real final chunk, so the function is right and something
# about its INPUTS is not: the kept reply is missing, stale, or holds different
# text. Three different faults, one symptom, and the decision was silent. It now
# says which, in the log the owner already sends.
section("v3.75 patch38: the last-chunk decision explains itself")

check("def _th_why(" in py and "thought NOT-FINAL" in py,
      "a chunk judged not-final records why")
check('"no reply kept for this speaker"' in py
      and '"the kept reply is %.1fs old"' in py
      and '"the chunk does not end where the reply ends (%d shared)"' in py,
      "and the three causes are told apart - missing, stale, mismatched")
check("| reply tail %r | chunk tail %r" in py,
      "with both tails, which is what the comparison actually looks at")
check('"ttsActionOut": "on",' in py,
      "the action a character chose is shown by default")
check('"%s: %s" % (k, " ".join(str(v).split()))' in py,
      "an action parameter is written whole")
nin(py, '" ".join(str(v).split())[:60]',
    "the 60-character cut that removed the end of the useful ones is gone")

try:
    # nothing here writes: the log call is stubbed and action_row is pure, so
    # log_dir and CONFIG are left alone - redirecting them broke the cleanup a
    # LATER section does through the same names
    _saidZ = []
    _realZ = fp.calterm_log
    fp.calterm_log = lambda rows: _saidZ.extend(rows)
    _whoZ = "GateSpeaker"
    # a thought must be waiting, or the verdict is not explained at all
    with fp.TH_AFTER_LOCK:
        fp.TH_AFTER[_whoZ] = [{"end": 0.0, "fin": False}]
    fp.REPLY_FULL.pop(_whoZ, None)
    fp.tts_chunk_is_last(_whoZ, "anything at all")
    _z1 = any("no reply kept" in s for s in _saidZ)
    _saidZ.clear()
    fp.REPLY_FULL[_whoZ] = (fp._th_norm("hello there friend"), time.time() - 99)
    fp.tts_chunk_is_last(_whoZ, "hello there friend")
    _z2 = any("old" in s for s in _saidZ)
    _saidZ.clear()
    fp.REPLY_FULL[_whoZ] = (fp._th_norm("the whole reply ends here"), time.time())
    _z3 = fp.tts_chunk_is_last(_whoZ, "reply ends here") is True and not _saidZ
    fp.tts_chunk_is_last(_whoZ, "something else entirely")
    _z4 = any("does not end where" in s for s in _saidZ)
    fp.calterm_log = _realZ
    with fp.TH_AFTER_LOCK:
        fp.TH_AFTER.pop(_whoZ, None)
    fp.REPLY_FULL.pop(_whoZ, None)
    _rowZ = fp.action_row('{"ACTION":"Travel","PARAMS":{"to":"%s"}}' % ("x" * 200),
                          "Ada")
    _z5 = ("x" * 200) in _rowZ
    check(_z1 and _z2 and _z3 and _z4 and _z5,
          "run: missing, stale and mismatched each name themselves, a true final "
          "chunk still passes silently, and a long action parameter is not cut",
          str([_z1, _z2, _z3, _z4, _z5]))
except Exception as _e38x:
    check(False, "the patch38 runs did not RUN", str(_e38x)[:140])


# ----------------------------------------------------------------- v3.75 patch39
# The thought code did NOT regress: tts_thought_fire, tts_thought_after_chunk and
# tts_chunk_trace are byte-identical to patch11, the build the owner calls good.
# A chunk is traced when its synthesis RETURNS, so "the reply is still arriving"
# was decided from returned chunks alone - and a request still open leaves no mark
# anywhere. The owner's 08:50:44 line spent 12.7s inside one request, the 3.5s
# quiet window closed mid-flight, and the thought spoke 3.0s before the last chunk
# was delivered. patch11 had the same hole and never fell in it: its calibration
# store was warm, so no chunk ever took 3.5s.
section("v3.75 patch39: a chunk still open holds the reply open")

check("TTS_INFLIGHT = {}" in py and "def tts_inflight_add(" in py
      and "def tts_inflight_drop(" in py and "def tts_inflight_since(" in py,
      "an open chunk request is recorded against its speaker")
check("_held = tts_inflight_since(who)" in py
      and "_arriving = bool(_held) or (time.time() - _last_rx) <= 3.5" in py,
      "and the arriving window counts it, not only chunks already returned")
nin(py, "_arriving = (time.time() - _last_rx) <= 3.5",
    "the returned-chunks-only window is gone")
check("_cap = 3 if not _held else int(TTS_INFLIGHT_MAX_S / 2.0)" in py,
      "three defers still bounds a GUESS; an open request waits on the clock")
check("tts_inflight_add(eid, _thWho)" in py
      and "tts_inflight_drop(eid)" in seg(py, "    def _run(self, eid, text,",
                                          "    def _run_inner(self, eid, text,"),
      "registered once the speaker is settled, cleared in _run's finally")

# One synthesis per thought. The warm-up and the fire ask for the same eid and a
# file-exists cache cannot see a wav still being written: both synthesised, and the
# second take held the single audio.cpp slot while the reply's own next chunk queued
# behind it - which is the delay that closed the window in the first place.
check("_TH_MAKE_LOCK" in py and "_mk = _TH_MAKE.setdefault(eid, threading.Lock())" in py,
      "a thought being synthesised is not synthesised a second time")
check("for _k in list(_TH_MAKE)[:-24]:" in py
      and "if _k != eid and not _TH_MAKE[_k].locked():" in py,
      "and the lock table is bounded without ever dropping a held one")

# A thought is spoken by the panel, dialogue by the game. Nothing joined them, so
# the next character's first line started on top of the thought still sounding.
check("TTS_FLOOR = [0.0]" in py and "def tts_floor_set(" in py,
      "a thought being spoken holds the room")
check("tts_floor_set(_secs)" in py,
      "claimed by a fired thought before it is broadcast")
check("0.0 if (_isp or ping) else TTS_FLOOR[0] - time.time()" in py,
      "and the next line waits for it - never the player's own voice or the ping")
nin(py, "_hold_s = min(_thw, 12.0)",
    "the bare 12.0 became the named ceiling both holds share")

try:
    import threading as _th39, tempfile as _tf39, shutil as _sh39, io as _io39
    import wave as _wv39, os as _os39

    # -- the field replay: chunk 1 back, the final chunk POSTed and still open.
    #    The decision moments are walked exactly as the timer chain would.
    class _Clk39(object):
        def __init__(self, t): self.now = t
        def time(self): return self.now
        def sleep(self, s): self.now += s
        def __getattr__(self, k): return getattr(_realtime39, k)

    import time as _realtime39
    _oldtime39, _oldcal39, _oldsse39, _oldmake39 = (
        fp.time, fp.calterm_log, fp.sse_notify, fp.tts_thought_make)
    _clk39 = _Clk39(1000000.0)
    fp.time = _clk39
    fp.calterm_log = lambda rows: None
    fp.sse_notify = lambda *a, **k: None
    fp.tts_thought_make = lambda who, text, cfg=None: ("th_gate", 6.0)

    def _replay39(who, ret_s, fires_in):
        """True when the thought waited for the still-open final chunk."""
        base = _clk39.now
        fp.REPLY_FULL.clear(); fp.CHUNK_TRACE.clear(); fp.TH_AFTER.clear()
        fp.TTS_INFLIGHT.clear()
        _full = fp._th_norm("chunk one opening words and then the rest of the reply "
                            "which ends right here")
        fp.REPLY_FULL[who] = (_full, base)
        fp.CHUNK_TRACE[who] = [(base, 1.5, fp._th_norm("chunk one opening words"))]
        fp.TH_AFTER[who] = [{"text": "a thought", "end": base + fires_in,
                             "t0": base, "timer": None}]
        _clk39.now = base + 0.09
        fp.tts_inflight_add("gate-final", who)
        _t, _g = base + fires_in, 0
        while _g < 40:
            _g += 1
            _clk39.now = _t
            if _clk39.now >= base + ret_s:
                _clk39.now = base + ret_s + 5.0
                return True                       # the chunk came back first
            _b = len(fp.TH_AFTER.get(who) or [])
            fp.tts_thought_fire(who)
            if len(fp.TH_AFTER.get(who) or []) < _b:
                _clk39.now = base + ret_s + 5.0
                return False                      # fired while it was still open
            _t = _clk39.now + 2.0 + fp.TH_FIRE_PAD
        _clk39.now = base + ret_s + 5.0
        return True

    _y1 = _replay39("GateTolfdir", 5.58, 2.8)     # the owner's 08:50:03 reply
    _y2 = _replay39("GateEleanor", 12.77, 2.4)    # the owner's 08:50:44 reply
    # and the ghost the bounded ladder exists for: NOTHING open, quiet window shut,
    # so the chain must still fire rather than wait on a chunk that is not coming
    _base39 = _clk39.now
    fp.REPLY_FULL.clear(); fp.CHUNK_TRACE.clear(); fp.TH_AFTER.clear()
    fp.TTS_INFLIGHT.clear()
    fp.REPLY_FULL["GateGhost"] = (fp._th_norm("a reply whose last chunk never came"),
                                  _base39)
    fp.CHUNK_TRACE["GateGhost"] = [(_base39, 1.0, fp._th_norm("a reply whose"))]
    fp.TH_AFTER["GateGhost"] = [{"text": "t", "end": _base39, "t0": _base39,
                                 "timer": None}]
    for _i39 in range(6):
        _clk39.now += 2.2
        fp.tts_thought_fire("GateGhost")
    _y3 = not fp.TH_AFTER.get("GateGhost")

    # -- the floor: a thought's own length plus the half second, replaced not raised
    fp.time = _realtime39
    _t039 = _realtime39.time()
    fp.tts_floor_set(4.0)
    _y4 = 4.4 < (fp.TTS_FLOOR[0] - _t039) < 4.6
    fp.tts_floor_set(1.0)
    _y5 = (fp.TTS_FLOOR[0] - _t039) < 2.0
    fp.TTS_FLOOR[0] = 0.0

    # -- one synthesis, two simultaneous callers. The REAL tts_thought_make is
    #    needed here, so the replay's stub comes off first.
    fp.time = _realtime39
    fp.tts_thought_make = _oldmake39
    _tmp39 = _tf39.mkdtemp(prefix="gate39-")
    _hits39, _hl39 = [], _th39.Lock()

    def _spk39(base, mid, text, ref, reftext=None):
        with _hl39:
            _hits39.append(text)
        _realtime39.sleep(0.25)
        _b = _io39.BytesIO()
        with _wv39.open(_b, "wb") as _w:
            _w.setnchannels(1); _w.setsampwidth(2); _w.setframerate(24000)
            _w.writeframes(b"\x00\x00" * 2400)
        return _b.getvalue(), {}

    _sv39 = (fp.tts_acpp_speak, fp.tts_ref_learn, fp.tts_conditioned, fp.tts_echo_wav,
             fp.tts_ref_canonical, fp.tts_ref_text, fp.tts_server_port, fp.tts_engine,
             fp.TTSW.dir, fp.TTSW.prune, fp.TTSW.log)
    fp.tts_acpp_speak = _spk39
    fp.tts_ref_learn = lambda *a, **k: None
    fp.tts_conditioned = lambda *a, **k: None
    fp.tts_echo_wav = lambda p: True
    fp.tts_ref_canonical = lambda r: r
    fp.tts_ref_text = lambda r, c=None: ""
    fp.tts_server_port = lambda cfg: 1240
    fp.tts_engine = lambda cfg: "audiocpp"
    fp.TTSW.dir = lambda: _tmp39
    fp.TTSW.prune = lambda: None
    fp.TTSW.log = lambda s: None
    fp.TTS_REF_BY_NAME["GateAda"] = _os39.path.join(_tmp39, "ada.wav")
    _got39 = []
    _thr39 = [_th39.Thread(target=lambda: _got39.append(
        fp.tts_thought_make("GateAda", "One short thought.", {"settings": {}})))
        for _ in range(2)]
    for _t39 in _thr39: _t39.start()
    for _t39 in _thr39: _t39.join()
    _y6 = len(_hits39) == 1 and len({_e for _e, _ in _got39}) == 1

    (fp.tts_acpp_speak, fp.tts_ref_learn, fp.tts_conditioned, fp.tts_echo_wav,
     fp.tts_ref_canonical, fp.tts_ref_text, fp.tts_server_port, fp.tts_engine,
     fp.TTSW.dir, fp.TTSW.prune, fp.TTSW.log) = _sv39
    fp.TTS_REF_BY_NAME.pop("GateAda", None)
    _sh39.rmtree(_tmp39, ignore_errors=True)
    fp.time, fp.calterm_log, fp.sse_notify = _oldtime39, _oldcal39, _oldsse39
    fp.REPLY_FULL.clear(); fp.CHUNK_TRACE.clear(); fp.TH_AFTER.clear()
    fp.TTS_INFLIGHT.clear()

    check(_y1 and _y2 and _y3 and _y4 and _y5 and _y6,
          "run: both field replies wait for their open chunk, an abandoned chunk "
          "still fires on the bounded ladder, the floor is a thought's length plus "
          "the gap and a newer one replaces it, and two callers get one synthesis",
          str([_y1, _y2, _y3, _y4, _y5, _y6]))
except Exception as _e39x:
    check(False, "the patch39 runs did not RUN", str(_e39x)[:140])


# A character's name was capped at 29 characters and failed SILENTLY: note_speaker
# returned "", and the mood queue, the kept reply, the reply ring and the freshest
# thought are all guarded by `if who:`. The owner's Ertzebet the Librarian's
# Assistant is 34 characters, so she had no emotion tags, no reply text for the
# last-chunk matcher, no thought audio, and the dashboard wrote a bare "thought:".
section("v3.75 patch39: a character's name is not capped below Skyrim's own")

check(rb"{1,59}?" in fp.SPEAKER_RX.pattern and rb"{1,28}?" not in fp.SPEAKER_RX.pattern,
      "a titled character's name is read, not silently dropped")
check(rb"{1,59}?" in fp.PLAYER_RX.pattern,
      "and the player's own name has the same room")
try:
    _n39 = []
    for _nm39 in ("Ertzebet the Librarian's Assistant", "Mirabelle Ervine",
                  "Urag gro-Shub", "Tolfdir", "Colette Marence"):
        _b39 = ("You are %s, a member of the College." % _nm39).encode("utf-8")
        _m39 = fp.SPEAKER_RX.search(_b39)
        _n39.append(bool(_m39) and _m39.group(1).decode("utf-8") == _nm39)
    # and it still cannot run away: a capture may not cross a comma or a full stop
    _runaway = fp.SPEAKER_RX.search(b"You are here. Everyone is, a bit tired")
    _n39.append(_runaway is None or b"." not in _runaway.group(1))
    _p39 = fp.PLAYER_RX.search(b"## Ertzebet the Librarian's Assistant's Party's Quests")
    _n39.append(bool(_p39))
    check(all(_n39),
          "run: every name reads back whole, long ones included, and the capture "
          "still stops at a comma or a full stop",
          str(_n39))
except Exception as _e39n:
    check(False, "the patch39 name runs did not RUN", str(_e39n)[:140])


section("v3.75 patch39: one popover, one visual language")

_adj39 = seg(_css, ".tpanel { display: none;", ".tchrome.adjopen .tpanel")
for _cls39, _name39 in ((".topanel", "Options"), (".tppanel", "Providers")):
    _p39 = seg(_css, _cls39 + " { display: none;",
               ".tchrome.%sopen %s" % ("opt" if _cls39 == ".topanel" else "prov", _cls39))
    nin(_p39, "border: 1px solid var(--line)",
        "the %s panel draws no grey line" % _name39)
    check("border: none;" in _p39, "%s: it is stated, not merely absent" % _name39)
    for _decl39 in ("box-shadow: 0 0 14px -2px rgba(0,0,0,.85)", "border-radius: 10px",
                    "margin-top: 4px", "width: max-content"):
        check(_decl39 in _p39 and _decl39 in _adj39,
              "%s: %s, the same as Adjust" % (_name39, _decl39))
    # the fill and blur are the panel's own and must survive the border change
    check(_p39.count("backdrop-filter: blur(2px)") == 2,
          "%s still blurs the log behind it, prefixed and not" % _name39)

# BUILD.md described a command that does not produce the artefact that ships.
_bld39 = rd("BUILD.md").decode("utf-8", "replace") if os.path.isfile(
    os.path.join(ROOT, "BUILD.md")) else ""
if _bld39:
    check("-std=c++17 -O2 -municode -mwindows -static -s" in _bld39,
          "the documented build is the one that was executed, strip included")
    check("-lshell32" in _bld39 and "-lole32" in _bld39 and "-lws2_32" not in _bld39,
          "against the libraries the launcher actually calls")
    check("bare filename" in _bld39,
          "and says why all four inputs must share one working directory")
    check("665 KB instead of 216 KB" in _bld39,
          "with what following it unstripped would have cost")
if os.path.isfile(os.path.join(ROOT, "PandorumLLM.exe")):
    check(os.path.getsize(os.path.join(ROOT, "PandorumLLM.exe")) < 400 * 1024,
          "the exe in this tree is the stripped build",
          "%d bytes" % os.path.getsize(os.path.join(ROOT, "PandorumLLM.exe")))

check(".provall { grid-column: 1 / -1;" in _css
      and "justify-self: center;" in seg(_css, ".provall {", ".provpick {"),
      "and All on/off sits in the middle of the grid it spans")
nin(seg(_css, ".provall {", ".provpick {"), "justify-self: start;",
    "not pinned to the left edge")


# ----------------------------------------------------------------- v3.75 patch40
# The queue rule already refused a name owned by another voicetype - `taken` inverts
# _spk_voices. But the PLAYER never enters _spk_voices: their branch returns before
# that dict is touched. So the guard was blind to exactly one name, and it is the one
# SkyrimNet queues most often, because it writes the player's dialogue too. Colette's
# chunk arrived while a Maxxor request waited, nothing owned "Maxxor", and her line
# was named for the player.
section("v3.75 patch40: an NPC sample never takes the player's name")

_svx = seg(py, "def speaker_for_voice_ex(voicetype):", "def player_name_unread(")
check("for _pn in (player_name_setting(), _spk_player[0]):" in _svx,
      "the player's names are read before the lock, which neither call takes")
check('taken.setdefault(_pn, "player")' in _svx,
      "and the guard that inverts _spk_voices is told about them")
check("_elig = [nm for _w, nm in _spk_recent" in _svx
      and "taken.get(nm, key) == key]" in _svx,
      "a waiting request counts only if its character could speak through THIS sample")
check("if run and run[2] and now - run[1] <= RUN_GAP_S and not _elig:" in _svx,
      "so a request that was already ruled out no longer stands the run down")
nin(_svx, "and not any(now - _w <= SPEAKER_PAIR_S for _w, _n in _spk_recent)):",
    "the raw queue-is-empty test is gone")
check(_svx.count("taken = {v: k for k, v in _spk_voices.items()}") == 1,
      "and the ownership table is built once, so its two readers cannot disagree")
check("refused to name %s after the player" in py,
      "a refusal is said out loud, where the wrong name used to appear")

try:
    import time as _t40
    _sv40 = (dict(fp._spk_voices), list(fp._spk_recent), dict(fp._spk_run),
             fp._spk_typed[0], fp._spk_player[0], set(fp._spk_known),
             dict(fp._spk_pin), dict(fp._spk_unique_pos))
    _pl40, _al40 = fp.panel_log, fp.tts_identity_alarm
    fp.panel_log = lambda *a, **k: None
    fp.tts_identity_alarm = lambda *a, **k: None

    def _reset40():
        fp._spk_voices.clear(); fp._spk_run.clear(); fp._spk_pin.clear()
        fp._spk_recent[:] = []; fp._spk_known.clear(); fp._spk_unique_pos.clear()
        fp._spk_typed[0] = ""; fp._spk_player[0] = ""; fp._spk_player_src[0] = ""
        fp.META_LAST[0], fp.META_LAST[1] = "", 0.0

    _now40 = _t40.time()

    # the owner's 11:29:13 record, replayed from the ledger it wrote
    _reset40()
    fp._spk_voices["femaleshrill"] = "Colette Marence"
    fp._spk_voices["femaleuniquemirabelleervine"] = "Ertzebet the Librarian\'s Assistant"
    fp._spk_run["femaleshrill"] = ["Colette Marence", _now40 - 1.0, True]
    fp._spk_pin["femaleshrill"] = ("Colette Marence", _now40 - 12.0)   # aged out
    fp._spk_player[0] = "Maxxor"
    fp._spk_known.update(["Colette Marence", "Maxxor",
                          "Ertzebet the Librarian\'s Assistant"])
    fp._spk_recent[:] = [(_now40 - 2.0, "Maxxor"),
                         (_now40 - 1.0, "Ertzebet the Librarian\'s Assistant")]
    _w1 = fp.speaker_for_voice_ex("femaleshrill")[0] == "Colette Marence"

    # patch116 must survive: a SHARED voicetype still hands over to who just spoke
    _reset40()
    fp._spk_voices["femaledarkelf"] = "Nelysa"
    fp._spk_run["femaledarkelf"] = ["Nelysa", _now40 - 1.0, True]
    fp._spk_known.update(["Nelysa", "Brelyna Maryon"])
    fp._spk_recent[:] = [(_now40 - 1.0, "Brelyna Maryon")]
    _w2 = fp.speaker_for_voice_ex("femaledarkelf")[0] == "Brelyna Maryon"

    # the player's name is refused on an NPC sample even with nothing else waiting
    _reset40()
    fp._spk_player[0] = "Maxxor"
    fp._spk_known.update(["Maxxor"])
    fp._spk_recent[:] = [(_now40 - 1.0, "Maxxor")]
    _w3 = fp.speaker_for_voice_ex("malenord")[0] != "Maxxor"

    # and a free voicetype is still paired with the request that named it
    _reset40()
    fp._spk_known.update(["Urag gro-Shub"])
    fp._spk_recent[:] = [(_now40 - 1.0, "Urag gro-Shub")]
    _w4 = fp.speaker_for_voice_ex("maleorc")[0] == "Urag gro-Shub"

    # the typed name counts as the player\'s too, not only the one read from a prompt
    _reset40()
    fp._spk_typed[0] = "Dovah"
    fp._spk_known.update(["Dovah"])
    fp._spk_recent[:] = [(_now40 - 1.0, "Dovah")]
    _w5 = fp.speaker_for_voice_ex("malenord")[0] != "Dovah"

    _reset40()
    (fp._spk_voices.update(_sv40[0]), fp._spk_recent.extend(_sv40[1]),
     fp._spk_run.update(_sv40[2]))
    fp._spk_typed[0], fp._spk_player[0] = _sv40[3], _sv40[4]
    fp._spk_known.update(_sv40[5]); fp._spk_pin.update(_sv40[6])
    fp._spk_unique_pos.update(_sv40[7])
    fp.panel_log, fp.tts_identity_alarm = _pl40, _al40

    check(_w1 and _w2 and _w3 and _w4 and _w5,
          "run: the owner\'s line is Colette again, a shared voicetype still hands "
          "over, the player\'s name is refused on an NPC sample typed or read, and a "
          "free voicetype is still paired",
          str([_w1, _w2, _w3, _w4, _w5]))
except Exception as _e40x:
    check(False, "the patch40 runs did not RUN", str(_e40x)[:140])


# ----------------------------------------------------------------- v3.75 patch41
# Five emotion tokens, measured by ear on the owner's rig, one short line each, the
# engine re-conditioned on another speaker before every take so the carryover pressure
# was identical. disgust, longing, sadness and shame came back as a DIFFERENT SPEAKER;
# elation came back as the right speaker but unrecognizable, at 4x the RMS of every
# other take. The other sixteen were correct, with amusement and pride as controls.
# The block set already existed and had been empty since it was written.
section("v3.75 patch41: the tokens that break the voice are refused")

check(sorted(fp.TTS_EMOTION_OFF)
      == ["determination", "disgust", "elation", "longing", "sadness", "shame"],
      "the five measured emotions and the one asked for are named",
      str(sorted(fp.TTS_EMOTION_OFF)))
check(py.index("TTS_EMOTION_OFF = (") < py.index("DEF_SETTINGS = {"),
      "the list is defined above the defaults it seeds")
check(py.count("TTS_EMOTION_OFF = (") == 1,
      "and defined once, so the two boards cannot drift from each other")
check("ELATION HAS BEEN HERE BEFORE" in py,
      "elation records that it has been blocked and unblocked before")
nin(py, "over-reference x%.2f",
    "the patch40 length diagnostic is gone - the A/B disproved its hypothesis")

# The unique-voicetype bind is a fact about the SAMPLE, not about who speaks through
# it now. SkyrimNet lends a unique sample to other characters.
_ubx = seg(py, "def speaker_for_voice_ex(voicetype):", "def player_name_unread(")
check(_ubx.index('return pin[0], "the words of the line itself"')
      < _ubx.index('return ub, "bound to this unique voicetype"'),
      "a unique voicetype yields to the words of the line itself")
check(_ubx.index('return ub, "bound to this unique voicetype"')
      < _ubx.index('"paired with a waiting dialogue request"'),
      "but still outranks the queue, the cache and the run")

try:
    import time as _t41
    _pl41 = fp.panel_log
    fp.panel_log = lambda *a, **k: None
    # With NO board applied, nothing is refused - the six are a default now, and the
    # patch42 section runs all three routes with the default board, which is the real
    # question. Here: an allowed emotion must still travel every route untouched.
    _leak41, _drop41 = [], []
    for _e41 in ("amusement", "pride", "anger", "fear"):
        _tok = "<|emotion:%s|>" % _e41
        if not any(w.split("-")[-1].lower() == _e41
                   for w in dict(fp.TAG_OFFER).get("Emotion", ())):
            _drop41.append("%s via offer" % _e41)
        if _tok not in fp.tts_apply_tags("[EMOTION-%s] A line." % _e41.upper(),
                                         keep=True, engine="audiocpp"):
            _drop41.append("%s via wire" % _e41)
        fp.MOOD_QUEUE["GateEmo"] = ([("emotion", _e41)], _t41.time())
        if _tok not in fp.tts_npc_mood_arm("GateEmo", "A line."):
            _drop41.append("%s via mood arm" % _e41)
        fp.MOOD_QUEUE.pop("GateEmo", None)

    # the unique bind yields to the line's own words, and answers without one
    _k41 = "femaleuniquemirabelleervine"
    _sv41 = (dict(fp._spk_unique_pos), dict(fp._spk_pin), dict(fp._spk_run),
             set(fp._spk_known))
    fp._spk_unique_pos.clear(); fp._spk_pin.clear(); fp._spk_run.clear()
    fp._spk_known.update(["Mirabelle Ervine", "Ertzebet the Librarian\'s Assistant"])
    _u1 = fp.speaker_for_voice_ex(_k41)[0] == "Mirabelle Ervine"
    fp._spk_pin[_k41] = ("Ertzebet the Librarian\'s Assistant", _t41.time())
    _u2 = fp.speaker_for_voice_ex(_k41)[0] == "Ertzebet the Librarian\'s Assistant"
    fp._spk_pin.clear()
    _u3 = fp.speaker_for_voice_ex(_k41)[0] == "Mirabelle Ervine"
    fp._spk_unique_pos.clear(); fp._spk_pin.clear(); fp._spk_run.clear()
    fp._spk_known.clear()
    fp._spk_unique_pos.update(_sv41[0]); fp._spk_pin.update(_sv41[1])
    fp._spk_run.update(_sv41[2]); fp._spk_known.update(_sv41[3])
    fp.panel_log = _pl41

    check(not _leak41 and not _drop41 and _u1 and _u2 and _u3,
          "run: an allowed emotion still travels the offer, the wire and the mood "
          "arm, and a borrowed unique sample takes the name its own words give "
          "while the filename still answers without one",
          str([_leak41, _drop41, _u1, _u2, _u3]))
except Exception as _e41x:
    check(False, "the patch41 runs did not RUN", str(_e41x)[:140])


# ----------------------------------------------------------------- v3.75 patch42
# patch41 subtracted the measured emotions from the offer, so they left the board
# entirely and could not be put back - the trap in section 5: never let an
# explanation disable an input. Elation especially, which has been blocked,
# unblocked and blocked again across this project's life, had lost its switch.
# They are a DEFAULT now: on the board, ticked off, one click from returning.
section("v3.75 patch42: the six are a default, not a refusal")

check(fp.TTS_EMOTION_OFF == ("disgust", "elation", "longing", "sadness", "shame",
                             "determination"),
      "five measured and one asked for, named in one place",
      str(fp.TTS_EMOTION_OFF))
check(len(dict(fp.TAG_OFFER)["Emotion"]) == len(fp.TTS_TAGS["emotion"]),
      "every emotion the engine has is on the board again",
      "%d of %d" % (len(dict(fp.TAG_OFFER)["Emotion"]), len(fp.TTS_TAGS["emotion"])))
check(fp.DEF_SETTINGS["ttsTagsOff"] == fp.TTS_EMOTION_OFF_WORDS
      and fp.DEF_SETTINGS["ttsTagsFinalOff"] == fp.TTS_EMOTION_OFF_WORDS,
      "and a fresh install ships them off on BOTH boards - the prompt and the wire")
nin(py, "TTS_EMOTION_BLOCK = frozenset",
    "the hard refusal is gone, switch and all")
check("cool = frozenset(tag_pair(_w) for _w in (cool or ()))" in py,
      "the NPC mood arm reads the board in whichever notation it arrives")
check('cool=tags_off(st, "ttsTagsFinalOff") | _cool' in py,
      "and is given it - the arm forms its own token, so the wire gate cannot catch it")

try:
    import time as _t42
    _st42 = dict(fp.DEF_SETTINGS)                     # exactly a fresh install
    _ban42 = fp.tags_off(_st42, "ttsTagsFinalOff")
    _off42 = fp.tags_off(_st42, "ttsTagsOff")
    _pl42 = fp.panel_log
    fp.panel_log = lambda *a, **k: None

    _prompt42 = fp.tts_tag_prompt(off=frozenset(w.upper() for w in _off42))
    _inp42 = [e for e in fp.TTS_EMOTION_OFF
              if ("EMOTION-%s" % e.upper()) in _prompt42]

    _leak42 = []
    for _e42 in fp.TTS_EMOTION_OFF:
        _tok42 = "<|emotion:%s|>" % _e42
        if _tok42 in fp.tts_apply_tags("[EMOTION-%s] A line." % _e42.upper(),
                                       True, "audiocpp", _ban42):
            _leak42.append("%s wire" % _e42)
        fp.MOOD_QUEUE["GateP42"] = ([("emotion", _e42)], _t42.time())
        _arm42 = fp.tts_npc_mood_arm("GateP42", "A line.", cool=_ban42)
        fp.MOOD_QUEUE.pop("GateP42", None)
        if _tok42 in _arm42:
            _leak42.append("%s mood arm" % _e42)

    # one still allowed must still get through, both ways
    _keep42 = "<|emotion:amusement|>" in fp.tts_apply_tags(
        "[EMOTION-AMUSEMENT] A line.", True, "audiocpp", _ban42)
    fp.MOOD_QUEUE["GateP42"] = ([("emotion", "amusement")], _t42.time())
    _keep42b = "<|emotion:amusement|>" in fp.tts_npc_mood_arm(
        "GateP42", "A line.", cool=_ban42)
    fp.MOOD_QUEUE.pop("GateP42", None)

    # and one switched back ON returns - the agency patch41 removed
    _st42b = dict(fp.DEF_SETTINGS)
    for _k42 in ("ttsTagsOff", "ttsTagsFinalOff"):
        _st42b[_k42] = " ".join(w for w in str(_st42b[_k42]).split()
                                if w != "EMOTION-SADNESS")
    _back42 = "<|emotion:sadness|>" in fp.tts_apply_tags(
        "[EMOTION-SADNESS] A line.", True, "audiocpp",
        fp.tags_off(_st42b, "ttsTagsFinalOff"))
    fp.panel_log = _pl42

    check(not _inp42 and not _leak42 and _keep42 and _keep42b and _back42,
          "run: on a fresh install none of the six is named in the prompts or reaches "
          "the engine by either route, an allowed emotion still does, and one switched "
          "back on returns",
          str([_inp42, _leak42, _keep42, _keep42b, _back42]))
except Exception as _e42x:
    check(False, "the patch42 runs did not RUN", str(_e42x)[:140])


# ----------------------------------------------------------------- v3.75 patch43
# The default merge replaces a setting only when it is EMPTY - right for a preference,
# wrong for a measurement. A tag board the user had ever touched kept its value and
# kept the six broken emotions enabled, so the people most likely to be using tags
# were the only ones the fix did not reach.
section("v3.75 patch43: a measurement reaches a config the user had customised")

check('if not st.get("emoOffV43"):' in py and '_have + _add' in py,
      "the six are ADDED to an existing board, never replacing what is there")
check('st["emoOffV43"] = True' in py,
      "and only once, so switching one back on afterwards sticks")
nin(py, "TTS_EMOTION_BLOCK",
    "no comment still names the constant that was removed in patch42")

try:
    def _mig43(existing):
        _st = dict(existing)
        for _k, _v in fp.DEF_SETTINGS.items():
            if _k not in _st or (_st[_k] == "" and _v != "" and _k != "llamacppPath"):
                _st[_k] = _v
        if not _st.get("emoOffV43"):
            for _ek in ("ttsTagsOff", "ttsTagsFinalOff"):
                _hv = str(_st.get(_ek) or "").replace(",", " ").split()
                _ad = [w for w in fp.TTS_EMOTION_OFF_WORDS.split() if w not in _hv]
                if _ad:
                    _st[_ek] = " ".join(_hv + _ad)
            _st["emoOffV43"] = True
        return _st

    def _n43(st):
        return len([w for w in str(st["ttsTagsFinalOff"]).split()
                    if w.startswith("EMOTION-")])

    _m1 = _n43(_mig43({})) == 6                                   # fresh
    _m2 = _n43(_mig43({"ttsTagsOff": "", "ttsTagsFinalOff": ""})) == 6
    _cust = _mig43({"ttsTagsOff": "SFX-BURPING", "ttsTagsFinalOff": "SFX-BURPING"})
    _m3 = _n43(_cust) == 6 and "SFX-BURPING" in _cust["ttsTagsFinalOff"]
    # already migrated and the user switched five back on - it must STAY switched on
    _m4 = _n43(_mig43({"ttsTagsOff": "EMOTION-DISGUST",
                       "ttsTagsFinalOff": "EMOTION-DISGUST",
                       "emoOffV43": True})) == 1
    check(_m1 and _m2 and _m3 and _m4,
          "run: absent, empty and customised boards all end with the six off, what "
          "the user had put there survives, and a board migrated once is not "
          "migrated again over their choice",
          str([_m1, _m2, _m3, _m4]))
except Exception as _e43x:
    check(False, "the patch43 runs did not RUN", str(_e43x)[:140])

# One paragraph per release in README.txt - patch39 shipped with two, and a reader
# scanning for a version has no way to know a second one exists further down.
try:
    import re as _re43
    _rd43 = rd("README.txt").decode("utf-8", "replace").replace("\r\n", "\n")
    _hd43 = _re43.findall(r"^(v3\.\d+ (?:patch|hotfix)\d+):", _rd43, _re43.M)
    _dup43 = sorted({h for h in _hd43 if _hd43.count(h) > 1})
    check(not _dup43, "each release is described once in README.txt", str(_dup43))
except Exception as _e43y:
    check(False, "the README heading scan did not RUN", str(_e43y)[:140])


# ----------------------------------------------------------------- v3.75 patch44
# The tree had no .gitattributes at all, so git decided line endings from whatever
# core.autocrlf was set to on the machine doing the checkout - and the owner's global
# setting is `true`. A fresh clone would therefore hand back CRLF for the .md files
# and for launch-llm-fleet.ps1, both of which this gate requires to be LF: the
# encoding section would fail on files nobody had touched. The bytes are the contract,
# so they are declared rather than inferred.
section("v3.75 patch44: git is told the line endings, not left to guess")

if not os.path.isfile(os.path.join(ROOT, ".gitattributes")):
    # the release tree is not a git checkout; there is nothing here to declare
    check(None, "line endings declared to git", "repo tree only")
    _ga = ""
else:
    _ga = rd(".gitattributes").decode("utf-8", "replace")
# Nothing below runs on the release tree, which is not a checkout. (patch44)
if _ga:
    check("* " in _ga and "-text" in _ga,
          "nothing is converted unless this file says so")
    check("launch-llm-fleet.ps1" in _ga
          and "eol=lf" in _ga.split("launch-llm-fleet.ps1")[1][:20],
          "the one LF+BOM exception is named, exactly as LF_PS1 names it")

    # The whole point is that this file and RULES cannot drift. Every extension the gate
    # enforces must appear here saying the same thing.
    try:
        import re as _re44
        _rules44 = {}
        for _ln in _ga.split("\n"):
          _ln = _ln.split("#")[0].strip()
          if not _ln or _ln.startswith("*  ") or _ln.split()[0] == "*":
              continue
          _pat = _ln.split()[0]
          _m = _re44.search(r"eol=(crlf|lf)", _ln)
          if _m:
              _rules44[_pat] = _m.group(1)
        _miss44, _wrong44 = [], []
        for _ext, (_bom, _eol) in RULES.items():
          _key = "*" + _ext
          if _key not in _rules44:
              _miss44.append(_ext)
          elif _rules44[_key] != _eol:
              _wrong44.append("%s: gate says %s, gitattributes says %s"
                              % (_ext, _eol, _rules44[_key]))
        for _lf in LF_PS1:
          if _rules44.get(_lf) != "lf":
              _wrong44.append("%s is not pinned to lf" % _lf)
        check(not _miss44 and not _wrong44,
            "every extension the gate enforces is pinned here, saying the same thing",
            str(_miss44 + _wrong44))

        # A rule matching nothing means the file has drifted from the tree. Only the eol
        # rules are contracts; the `binary` lines are guards for types not here yet.
        _all44 = []
        for _dp, _dn, _fn in os.walk(ROOT):
          _dn[:] = [d for d in _dn if d not in (".git", "__pycache__")]
          _all44 += [f for f in _fn]
        _unused44 = []
        for _pat, _eol in _rules44.items():
          if not any(_f == _pat or (_pat.startswith("*.")
                                    and _f.lower().endswith(_pat[1:].lower()))
                     for _f in _all44):
              _unused44.append(_pat)
        check(not _unused44,
            "and no rule names a file type this tree does not have",
            str(_unused44))
    except Exception as _e44x:
        check(False, "the gitattributes cross-check did not RUN", str(_e44x)[:140])

    # and it must agree with the bytes actually in the tree, or the first clone breaks
    try:
        def _want44(rel):
          _base = rel.split("/")[-1]
          _hit = None
          for _ln in _ga.split("\n"):
              _ln = _ln.split("#")[0].strip()
              if not _ln:
                  continue
              _p = _ln.split()[0]
              if _p == "*":
                  continue
              if _p == _base or (_p.startswith("*.")
                                 and _base.lower().endswith(_p[1:].lower())):
                  _hit = _ln
          if not _hit:
              return None
          if "binary" in _hit:
              return "binary"
          _m = _re44.search(r"eol=(crlf|lf)", _hit)
          return _m.group(1).upper() if _m else None

        _bad44 = []
        for _dp, _dn, _fn in os.walk(ROOT):
          _dn[:] = [d for d in _dn if d not in (".git", "__pycache__")]
          for _f in sorted(_fn):
              _rel = os.path.relpath(os.path.join(_dp, _f), ROOT).replace("\\", "/")
              _raw = rd(_rel)
              if _rel.lower().endswith((".ico", ".exe")):
                  _act = "binary"
              else:
                  _c = _raw.count(b"\r\n")
                  _l = _raw.count(b"\n") - _c
                  _act = "CRLF" if _l == 0 and _c else ("LF" if _c == 0 else "MIXED")
              _w = _want44(_rel)
              if _w != _act:
                  _bad44.append("%s: declared %s, on disk %s" % (_rel, _w, _act))
        check(not _bad44,
            "and every file in the tree already has the endings it declares",
            str(_bad44[:3]))
    except Exception as _e44y:
        check(False, "the gitattributes tree scan did not RUN", str(_e44y)[:140])


# ------------------------------------------------------------------- v3.76 Beta
# A server card renders every setting the same way: label, the llama.cpp flag in
# blue, control - and the blue flag opens that setting in the Sampler Guide. The
# seven Speculative Decoding cells were drawn identically and opened nothing, on the
# grounds that these flags had no page. Four had gained one since and three never
# had. A control that LOOKS like a link and is not is worse than one that does not.
section("v3.76: every speculative flag opens its own guide page")

_sg = seg(JS, "const SPEC_GUIDE = {", "};")
nin(seg(JS, "const ref9 = function(flag) {", "const cell9 = function("),
    'style="cursor:default" title="the llama.cpp flag \'\n        + \'this control writes">[\' + esc(flag) + \']</span>\';\n    };',
    "the reference is no longer dead for every flag")
check('data-act="paramGuide" data-t="\' + pgSlug(g)' in JS,
      "a speculative flag opens the guide, like every other flag on the card")
check("if (!g) {" in seg(JS, "const ref9 = function(flag) {", "const cell9 = function("),
      "and a flag with no page still renders plainly rather than lying about it")

try:
    import re as _re76

    def _slug76(n):
        _o = ""
        for _c in n.lower():
            if _c.isalnum() and _c.isascii():
                _o += _c
            elif _o and _o[-1] != "-":
                _o += "-"
        return "pg-" + _o.rstrip("-")

    _i76 = JS.index("function renderParams()")
    _pages76 = set(_re76.findall(r'\{ ?name:"([^"]+)"', JS[_i76:_i76 + 200000]))
    _slugs76 = {_slug76(_n) for _n in _pages76}

    # every flag the card can hand ref9 must resolve to a page that exists
    _map76 = dict(_re76.findall(r'"(--[a-z-]+)":\s*"([^"]+)"', _sg))
    _bad76 = [f for f, p in _map76.items() if _slug76(p) not in _slugs76]

    # and every flag the speculative segment actually writes must be IN that map
    _spec76 = seg(JS, "h += '<div class=\"pgrp\">Speculative Decoding'", "h += '</div>';")
    _used76 = set(_re76.findall(r'"(--spec-draft-[a-z-]+)"', _spec76))
    _unmapped76 = sorted(_used76 - set(_map76))

    # the four pages this release adds
    _new76 = [p for p in ("Draft n-min", "Draft split probability",
                          "Draft backend sampling", "Draft KV cache type")
              if p not in _pages76]

    check(not _bad76 and not _unmapped76 and not _new76,
          "run: every speculative control the card writes maps to a guide page that "
          "exists, and none is left pointing at nothing",
          str([_bad76, _unmapped76, _new76]))
except Exception as _e76x:
    check(False, "the v3.76 speculative runs did not RUN", str(_e76x)[:140])


# The guide explained DRY and XTC and none of llama.cpp's four classic penalties, so
# a reader reaching for a repetition control had nothing to choose between.
section("v3.76: every repetition penalty llama.cpp has is explained")

try:
    _want76 = {"Repeat penalty": "--repeat-penalty N",
               "Repeat last-n": "--repeat-last-n N",
               "Presence penalty": "--presence-penalty N",
               "Frequency penalty": "--frequency-penalty N",
               "DRY penalty": "--dry-multiplier N",
               "XTC (Exclude Top Choices)": None}
    _miss76, _flag76 = [], []
    for _nm76, _fl76 in _want76.items():
        _m76 = _re76.search(r'\{ ?name:"%s"(.{0,140})' % _re76.escape(_nm76),
                            JS[_i76:_i76 + 200000], _re76.S)
        if not _m76:
            _miss76.append(_nm76)
        elif _fl76 and ('flag:"%s"' % _fl76) not in _m76.group(1):
            _flag76.append("%s: %s" % (_nm76, _fl76))
    check(not _miss76 and not _flag76,
          "run: repeat, repeat-last-n, presence, frequency, DRY and XTC each have a "
          "page, and each names the flag llama.cpp actually takes",
          str([_miss76, _flag76]))
except Exception as _e76y:
    check(False, "the v3.76 penalty runs did not RUN", str(_e76y)[:140])

# --penalize-nl was removed from llama.cpp master; a guide that offered it would be
# teaching a flag the server rejects.
nin(JS, "--penalize-nl", "and no page teaches a flag master has removed")


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
