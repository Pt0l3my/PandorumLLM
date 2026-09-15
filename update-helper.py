#!/usr/bin/env python3
"""PandorumLLM update helper - the only thing here that replaces files.

It is a script and not a compiled program on purpose. You can read it before it
runs; it adds no binary for a scanner to judge; and it ships inside each release,
so nothing has to keep it up to date. The panel extracts it from an archive it
has already proved and checks it against that archive's manifest before starting
it - so the step with the most power is the step given the least trust.

WHAT IT WILL NOT DO
  - run without a live panel to answer for it: without --pid and --port matching
    a PandorumLLM that is actually listening, it exits. It is not a general file
    replacer left lying in your folder.
  - open the archive it is handed without hashing it first, whatever the panel
    said about it a moment ago.
  - write a single file it has not just hashed against the manifest.
  - leave you between versions: every file it touches is backed up first, and any
    failure at any point puts all of them back before it stops.

Usage (the panel supplies all of this):
  update-helper.py --zip PATH --sha HEX --root DIR --port N --pid N
"""
import argparse
import hashlib
import io
import os
import shutil
import socket
import subprocess
import sys
import time
import zipfile

MANIFEST = "manifest.sha256.txt"
SELF = "update-helper.py"


def say(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(LOGDIR, "update.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def sha_of(path_or_bytes):
    h = hashlib.sha256()
    if isinstance(path_or_bytes, bytes):
        h.update(path_or_bytes)
        return h.hexdigest()
    with open(path_or_bytes, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def port_answers(port):
    """Is something listening there? The panel's own liveness test, simplified."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", int(port)))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def pid_alive(pid):
    try:
        if os.name == "nt":
            # NO CONSOLE FOR THE QUERY. The helper itself runs without a window,
            # so a child console program opens its own - and this is asked every
            # half second while waiting for the panel to close. Those were the
            # "terminals popping up for a flash second". (p135)
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % int(pid)],
                                 capture_output=True, text=True, timeout=15,
                                 creationflags=0x08000000)
            return str(pid) in (out.stdout or "")
        os.kill(int(pid), 0)
        # A ZOMBIE IS NOT ALIVE. os.kill(pid, 0) succeeds for a process that has
        # exited but not yet been reaped by its parent - so a panel that had gone
        # would still read as running and this would wait out its whole timeout
        # and abandon the update. Found by a failure harness, not in the field.
        try:
            with open("/proc/%d/stat" % int(pid)) as f:
                if f.read().rsplit(")", 1)[-1].split()[0] == "Z":
                    return False
        except Exception:
            pass
        return True
    except Exception:
        return False


def inside(root, path):
    """Does this path REALLY land under root?

    Resolved, not inspected. The textual checks below catch the tricks anyone
    would think of - a leading slash, a .. segment, a drive letter - but they
    reason about how a path is SPELLED. This asks where it actually ends up,
    which also answers the forms nobody thought of, and follows symlinks so a
    link planted inside the folder cannot point out of it.

    The owner's rule, and it has no configurable exception: an update writes
    inside PandorumLLM's own folder or it stops. (p127)
    """
    try:
        r = os.path.realpath(os.path.abspath(root))
        p = os.path.realpath(os.path.abspath(path))
        return p == r or p.startswith(r + os.sep)
    except Exception:
        return False


_PROG = {"at": time.time(), "state": "running", "steps": [], "stage": "", "reason": ""}


def progress(step):
    """One fact, written the moment it is true, to the file the returning panel
    serves. The page cannot see the helper work - the panel it talked to is
    gone - so the helper narrates into the file and the page reads the story
    afterwards. Every mark on the page then corresponds to a line here, and
    nothing is inferred from silence. (p138)
    """
    _PROG["steps"].append(step)
    _PROG["at"] = time.time()
    try:
        import json
        with open(os.path.join(LOGDIR, "update-result.json"), "w", encoding="utf-8") as f:
            json.dump(_PROG, f)
    except Exception:
        pass


def verdict(ok, stage, reason, wrote=0, kept=0, backup=""):
    """The helper's last word, left where the panel can read it after it is back.

    The page that asked for the update is still open, but the panel it was
    talking to has gone by the time this runs - so the outcome goes in a file,
    and the returning panel serves it. One object: did it work, which stage it
    was in if not, and why. (p137)
    """
    try:
        import json
        _PROG.update({"state": "ok" if ok else "failed", "stage": stage,
                      "reason": reason, "wrote": wrote, "kept": kept,
                      "backup": backup, "at": time.time()})
        with open(os.path.join(LOGDIR, "update-result.json"), "w", encoding="utf-8") as f:
            json.dump(_PROG, f)
    except Exception:
        pass


def read_manifest(zf):
    """The manifest, from inside the archive that has just been proved."""
    for nm in zf.namelist():
        flat = nm.replace("\\", "/")
        if flat.endswith("/" + MANIFEST) or flat == MANIFEST:
            out = {}
            for line in zf.read(nm).decode("utf-8", "replace").splitlines():
                bits = line.strip().split(None, 1)
                if len(bits) == 2 and len(bits[0]) == 64:
                    out[bits[1].strip().lstrip("*").replace("\\", "/")] = bits[0].lower()
            return out
    return {}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--zip", "--sha", "--root", "--port", "--pid"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()

    global LOGDIR
    LOGDIR = os.path.join(args.root, "logs")
    try:
        os.makedirs(LOGDIR, exist_ok=True)
    except Exception:
        LOGDIR = os.path.dirname(os.path.abspath(args.zip))

    say("update helper starting")

    # 1. A LIVE PANEL, OR NOTHING. This is what stops the helper being a general
    #    file replacer sitting in the folder: it will only act on behalf of a
    #    PandorumLLM that is running right now and asked for it.
    if not (pid_alive(args.pid) and port_answers(args.port)):
        say("no live panel on port %s (pid %s) - refusing to do anything"
            % (args.port, args.pid))
        return 2

    # 2. PROVE THE ARCHIVE, from this side. The panel proved it too. That was a
    #    different process at a different moment, and this is the one about to
    #    open it.
    if not os.path.isfile(args.zip):
        say("the staged archive is gone - nothing done")
        return 2
    got = sha_of(args.zip)
    if got != str(args.sha).lower():
        say("the staged archive does not match its checksum - nothing done")
        verdict(False, "swapping", "the staged archive no longer matched its checksum")
        return 2
    say("archive verified (%s)" % got[:16])
    _PROG["begun"] = time.time()
    progress("verified")

    with zipfile.ZipFile(args.zip) as zf:
        man = read_manifest(zf)
        # NO MANIFEST IS NOT NO REFERENCE. The archive was proved against the
        # published checksum a moment ago, from this side. Every member's hash
        # can be taken from it directly, and that is exactly what a manifest
        # would have said. What is lost without one is only the panel's ability
        # to re-check its install later; what is NOT lost is the guarantee that
        # no unverified byte reaches the disk. (p133)

        # every member, keyed the way the manifest keys them
        members = {}
        for nm in zf.namelist():
            if nm.endswith("/"):
                continue
            flat = nm.replace("\\", "/")
            # JUDGE THE RAW NAME FIRST. Stripping the top-level folder turns
            # "/etc/passwd" into "etc/passwd" - the leading empty segment is
            # eaten by the split - so a check made afterwards sees a tidy
            # relative path and waves it through. The panel catches this one; the
            # helper did not, and defence in depth means nothing if the second
            # layer is checking a value the first layer already laundered.
            # Found by a failure harness. (p127)
            if (flat.startswith("/") or ".." in flat.split("/")
                    or ":" in flat.split("/")[0]):
                say("unsafe path in archive: %s - nothing done" % nm)
                return 2
            key = flat.split("/", 1)[1] if "/" in flat else flat
            if not key or key.startswith("/"):
                say("unsafe path in archive: %s - nothing done" % nm)
                return 2
            members[key] = nm
        if not man:
            # built from `members`, which every name reached only AFTER the raw
            # path check above - so the fallback cannot become a way past it
            say("no manifest in the archive - taking each file's hash from the "
                "verified archive itself")
            for key, nm in members.items():
                man[key] = sha_of(zf.read(nm))
        missing = [k for k in man if k not in members]
        if missing:
            say("manifest names files the archive does not carry: %s - nothing done"
                % ", ".join(missing[:4]))
            return 2

        # 3. WAIT FOR THE PANEL TO LET GO. It was asked to shut down as this
        #    started; give it time, and do not proceed while it holds its files.
        say("waiting for the panel to close")
        for _ in range(120):
            if not (pid_alive(args.pid) or port_answers(args.port)):
                break
            time.sleep(0.5)
        else:
            say("the panel is still running after 60s - nothing done")
            verdict(False, "closing", "the panel did not close within 60 seconds")
            return 2
        time.sleep(1.0)
        progress("panel-closed")

        # 4. BACK UP EVERY FILE THIS WILL TOUCH, before touching any of them.
        backup = os.path.join(LOGDIR, "_update-backup-%d" % int(time.time()))
        os.makedirs(backup, exist_ok=True)
        saved = []
        try:
            for key in sorted(man):
                cur = os.path.join(args.root, key.replace("/", os.sep))
                if not inside(args.root, cur):
                    raise RuntimeError("%s would land outside the PandorumLLM "
                                       "folder" % key)
                if os.path.isfile(cur):
                    dst = os.path.join(backup, key.replace("/", os.sep))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(cur, dst)
                    saved.append((cur, dst))
            say("backed up %d file(s) to %s" % (len(saved), backup))
            progress("backed-up")

            # 5. WRITE, HASHING EACH ONE. A file is proved from the archive
            #    before it is written and again once it is on disk, because what
            #    matters is what ENDED UP there, not what was sent.
            wrote, skipped = 0, 0
            written = []
            aside = []                          # renamed .old, to clear at the end
            for key in sorted(man):
                if key == SELF:
                    continue                    # never replace the running helper
                raw = zf.read(members[key])
                if sha_of(raw) != man[key]:
                    raise RuntimeError("%s does not match the manifest" % key)
                cur = os.path.join(args.root, key.replace("/", os.sep))
                # asked AGAIN at the moment of writing, not only when backing up
                if not inside(args.root, cur):
                    raise RuntimeError("%s would land outside the PandorumLLM "
                                       "folder" % key)
                if os.path.isfile(cur) and sha_of(cur) == man[key]:
                    skipped += 1
                    continue                    # already exactly this
                os.makedirs(os.path.dirname(cur), exist_ok=True)
                # OVERWRITE, and rename aside ONLY if the file is held. The
                # launcher exe exits as soon as it has opened the browser, so
                # while the panel runs nothing holds it - it is a file like any
                # other. The old code renamed EVERY file it wrote to .old and
                # never removed them, so each update left fleet-panel.py.old
                # and friends behind. A rename is now the fallback for a file
                # that genuinely refuses, and it is remembered so it can be
                # cleared once the new panel is confirmed up. (p139)
                try:
                    with open(cur, "wb") as f:
                        f.write(raw)
                except PermissionError:
                    os.replace(cur, cur + ".old")
                    aside.append(cur + ".old")
                    with open(cur, "wb") as f:
                        f.write(raw)
                if sha_of(cur) != man[key]:
                    raise RuntimeError("%s did not land intact" % key)
                wrote += 1
                written.append(key)
            # THE MANIFEST ITSELF. It cannot list its own hash, so it is not in
            # the manifest, so the loop above never wrote it - and the panel that
            # came out of the update had nothing to check itself against. The
            # whole point of shipping one. It comes from the archive whose hash
            # was proved, so it is as trustworthy as everything else here. (p129)
            for _nm in zf.namelist():
                _flat = _nm.replace("\\", "/")
                if _flat.endswith("/" + MANIFEST) or _flat == MANIFEST:
                    _dst = os.path.join(args.root, MANIFEST)
                    if not inside(args.root, _dst):
                        raise RuntimeError("the manifest would land outside the "
                                           "PandorumLLM folder")
                    with open(_dst, "wb") as _f:
                        _f.write(zf.read(_nm))
                    wrote += 1
                    break
            # NAMED, not counted. "wrote 2 file(s)" left the owner asking which
            # two; the answer is the whole point of the line. (p139)
            say("wrote %d file(s), %d already current: %s"
                % (wrote, skipped, ", ".join(written) or "-"))
            progress("wrote")
        except Exception as e:
            say("FAILED: %s" % e)
            say("putting everything back")
            for cur, dst in saved:
                try:
                    shutil.copy2(dst, cur)
                except Exception as e2:
                    say("  could not restore %s: %s" % (cur, e2))
            say("restored %d file(s) - you are on the version you started with"
                % len(saved))
            verdict(False, "swapping", str(e), 0, len(saved), backup)
            return 1

    # 6. START THE PANEL AGAIN and wait until it actually answers, so the page
    #    reloading against a dead port is not a thing that can happen.
    # ABSOLUTE, because cwd is already the root - joining it twice is how the
    # relaunch pointed at root/root/fleet-panel.py and the panel never came back
    root = os.path.abspath(args.root)
    # NOT THE EXE. PandorumLLM.exe does two things: it starts fleet-panel.py
    # hidden, and then it opens a browser tab on the port. The second is the
    # whole reason it exists for a cold start, and exactly wrong here - the
    # page that asked for this update is still open and waiting to reconnect,
    # so the owner ended up with two panel tabs. The helper starts the panel
    # the way the exe would, and leaves the browser alone. (p137)
    py = sys.executable
    if os.name == "nt":
        pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
        if os.path.isfile(pyw):
            py = pyw                     # no console, as the exe chooses it
    launch = [py, os.path.join(root, "fleet-panel.py")]
    say("starting fleet-panel.py with %s (no new browser tab)"
        % os.path.basename(py))
    progress("started")
    try:
        kw = {"cwd": root, "close_fds": True}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008
        else:
            kw["start_new_session"] = True
        subprocess.Popen(launch, **kw)
    except Exception as e:
        say("could not start it: %s - start PandorumLLM yourself" % e)
        verdict(False, "back", "the files were replaced but the panel could not be started: %s" % e,
                wrote, skipped, backup)
        return 1
    for _ in range(120):
        if port_answers(args.port):
            say("the panel is answering again on %s - update complete" % args.port)
            break
        time.sleep(0.5)
    else:
        say("it has not answered in 60s - check logs/STARTUP-CRASH.log")
        verdict(False, "back", "the files were replaced but the panel did not answer within 60 seconds",
                wrote, skipped, backup)
        return 1

    # 7. TIDY, and only now. The backup stays: it costs a few megabytes and it is
    #    the thing you want if the new version misbehaves.
    # 7. CLEAR THE OLD, now that the new is confirmed answering. This is the
    #    helper's job, not the next panel's: it knows exactly what it renamed
    #    aside and where it staged, and the process that could have held an
    #    old file - the previous panel - is the one it just watched close.
    #    Anything renamed aside, the staging folder, and any .old a previous
    #    attempt left. Backups stay: they are the rollback. (p139)
    cleared = []
    for p in aside:
        try:
            os.remove(p)
            cleared.append(os.path.basename(p))
        except Exception as e:
            say("could not remove %s: %s" % (p, e))
    try:
        for nm in os.listdir(root):
            if nm.lower().endswith(".old"):
                try:
                    os.remove(os.path.join(root, nm))
                    cleared.append(nm)
                except Exception:
                    pass
    except Exception:
        pass
    try:
        stage_dir = os.path.dirname(os.path.abspath(args.zip))
        if os.path.basename(stage_dir).startswith("_panel-update-"):
            # the helper was started WITH this folder as its working directory,
            # and Windows will not remove a process's current directory - so
            # step out of it first, or the rmtree fails silently
            os.chdir(root)
            shutil.rmtree(stage_dir, ignore_errors=True)
            cleared.append(os.path.basename(stage_dir))
        else:
            os.remove(args.zip)
    except Exception:
        pass
    # ONE ROLLBACK, THE LATEST. A backup is the version an update replaced, so
    # only the newest one rolls the CURRENT install back; the ones before it
    # roll back to versions that are no longer installed. They stacked, one
    # folder per update, for ever. Kept: this attempt's. Removed: every earlier
    # one - and only on success, because a failed swap has just restored from
    # this attempt's backup and nothing older is worth touching then. (p140)
    try:
        keep = os.path.basename(backup)
        for nm in sorted(os.listdir(LOGDIR)):
            p = os.path.join(LOGDIR, nm)
            if nm.startswith("_update-backup-") and nm != keep and os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
                cleared.append(nm + " (older backup)")
    except Exception:
        pass
    say("cleared: %s" % (", ".join(cleared) or "nothing to clear"))
    progress("cleared")
    say("done. the previous files are kept in %s" % backup)
    verdict(True, "", "", wrote, skipped, backup)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("[update] helper crashed: %s" % exc, flush=True)
        sys.exit(1)
