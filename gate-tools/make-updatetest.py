#!/usr/bin/env python3
"""Build the update-test copy from a release tree.

The dummy is the current build wearing an older version tag, so it reads the
real release as newer and exercises the real updater. That means it is only
useful while it matches the build it was made from - twice now it has been
tested with an updater two patches behind, and both times the test measured the
old code and found the old bug.

So it is generated, never edited: run it against the release tree at package
time and the dummy cannot be stale.

    python3 gate-tools/make-updatetest.py <release-tree> <out-dir> [tag]
"""
import os
import re
import shutil
import subprocess
import sys

DEFAULT_TAG = "v3.74-updatetest"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2])
    tag = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_TAG
    if not os.path.isfile(os.path.join(src, "fleet-panel.py")):
        print("not a release tree: %s" % src)
        return 2

    dest = os.path.join(out, "PandorumLLM")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    shutil.copytree(src, dest)

    # the tag, and nothing else. A dummy that differs from its parent in any
    # other way is testing something that was never shipped
    p = os.path.join(dest, "fleet-panel.py")
    with open(p, encoding="utf-8", newline="") as f:
        t = f.read()
    m = re.search(r'APP_RELEASE_TAG = "([^"]+)"', t)
    if not m:
        print("no release tag found")
        return 2
    parent = m.group(1)
    t = t.replace('APP_RELEASE_TAG = "%s"' % parent,
                  'APP_RELEASE_TAG = "%s"' % tag, 1)
    # THE DUMMY SAYS WHAT IT IS. APP_PATCH alone made the header read
    # "v3.76-p74 Beta" - a version that does not exist - and every dummy zip
    # carried the same name, so nothing told the owner which build he was
    # holding; he ran a patch134 dummy after patch135 had been delivered and
    # reported patch134's faults. The header carries the tag AND the parent
    # now, and so does the zip. (p136)
    t = re.sub(r'APP_VERSION = "[^"]+"', 'APP_VERSION = "%s from %s"' % (tag, parent), t, count=1)
    t = re.sub(r"APP_PATCH = \d+ ", "APP_PATCH = 0 ", t, count=1)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    # the tree it came from keeps CRLF; a rewrite must not quietly change that
    with open(p, "rb") as f:
        d = f.read()
    d = re.sub(rb"(?<!\r)\n", b"\r\n", d)
    with open(p, "wb") as f:
        f.write(d)

    # a manifest of ITSELF, so the dummy reports its own files as matching
    # rather than inheriting its parent's list and calling itself changed
    mk = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "make-manifest.py")
    for junk in ("manifest.sha256.txt",):
        try:
            os.remove(os.path.join(dest, junk))
        except OSError:
            pass
    shutil.rmtree(os.path.join(dest, "logs"), ignore_errors=True)
    shutil.rmtree(os.path.join(dest, "__pycache__"), ignore_errors=True)
    subprocess.run([sys.executable, mk, dest], check=True,
                   stdout=subprocess.DEVNULL)

    with open(os.path.join(out, "FROM.txt"), "w", encoding="utf-8") as f:
        f.write("%s built from %s\n" % (tag, parent))
    print("update-test build: %s -> %s   (from %s)" % (tag, dest, parent))
    print("zip this as: PandorumLLM-%s-from-%s.zip" % (tag, parent.replace("v3.76-beta-", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
