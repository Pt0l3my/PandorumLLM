#!/usr/bin/env python3
"""Write manifest.sha256.txt for a release tree.

Every file the release ships, with its SHA-256, one per line, in the format
`sha256  relative/path`. The update helper checks each file against this as it
writes it, and the panel checks the whole install against it at start - so the
question "did that update land correctly" has an answer instead of an assumption.

Run at package time, before the zip is built:
    python3 gate-tools/make-manifest.py <release-tree>

The manifest cannot list itself (its hash would have to be known before it was
written), and nothing else needs to: the archive carrying it is verified as a
whole by the checksum published beside it, so the manifest inherits that proof.
"""
import hashlib
import os
import sys

NAME = "manifest.sha256.txt"
SKIP_DIRS = {"__pycache__", "logs", ".git"}
# per-install state is never listed: the two model ledgers, the config, the port
# file and the owned-take list are written by the panel on the machine it runs on.
# tts-model-kinds.json WAS listed through patch175, so every update delivered the
# developer's copy over the user's own and the start-up check then reported the
# panel's own cache as a changed file. (p177)
SKIP_FILES = {NAME, "tts-model-kinds.json", "model-kinds.json", "fleet-config.json",
              "panel-port.txt", "tts-own.json"}


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        print("not a directory: %s" % root)
        return 2
    rows = []
    for here, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES:
                continue
            p = os.path.join(here, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            rows.append((rel, h.hexdigest()))
    # LF endings and sorted order, so the same tree always produces the same
    # manifest byte for byte - a manifest that varied run to run would make the
    # release zip's own checksum meaningless as a comparison
    out = "".join("%s  %s\n" % (h, rel) for rel, h in sorted(rows))
    with open(os.path.join(root, NAME), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("%s: %d files" % (NAME, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
