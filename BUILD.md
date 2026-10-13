# Building PandorumLLM.exe

The exe is a small C++ launcher that starts `fleet-panel.py` and opens the browser. It is
**not** committed — it is built and attached to a Release. The panel itself needs no build
step; it is plain Python.

## What you need

MinGW-w64 (`x86_64-w64-mingw32-g++` and `x86_64-w64-mingw32-windres`).

- Debian/Ubuntu/WSL: `sudo apt-get install mingw-w64`
- Windows: MSYS2, then `pacman -S mingw-w64-x86_64-gcc`

## Build

`app.rc` names `app.manifest` and `PandorumLLM.ico` by **bare filename**, so all four
inputs must sit in the working directory windres runs in, or the icon and the manifest
vanish from the binary without an error.

```
S=/path/to/PandorumLLM/launcher-src
mkdir -p /tmp/exebuild && cd /tmp/exebuild
cp "$S/launcher.cpp" "$S/app.rc" "$S/app.manifest" "$S/PandorumLLM.ico" .

x86_64-w64-mingw32-windres app.rc -O coff -o app.res

x86_64-w64-mingw32-g++ -std=c++17 -O2 -municode -mwindows -static -s \
    launcher.cpp app.res -o PandorumLLM.exe -lshell32 -lole32
```

Every flag is load-bearing:

| flag | what breaks without it |
|---|---|
| `-municode` | `wWinMain` is not found; the link fails on `undefined reference to WinMain` |
| `-mwindows` | a console subsystem exe - a black cmd window on every launch |
| `-static` | the exe needs `libstdc++-6.dll`, `libgcc_s_seh-1.dll` and `libwinpthread-1.dll` beside it |
| `-s` | symbols are kept: 665 KB instead of 216 KB, no functional harm |
| `-lshell32` | `ShellExecute`, which opens the browser, fails to link |
| `-lole32` | the COM init behind that shell call fails to link |
| `windres -O coff` | wrong object format; the linker rejects the resource |

Verify afterwards - `file PandorumLLM.exe` must say **PE32+ executable (GUI) x86-64**,
which is the check that catches a missing `-mwindows`. The version strings live in the
resource section as UTF-16LE, so searching the binary for plain ASCII `3.75.0.0` finds
nothing and looks like a failure when the build is fine.

Rebuilding is only needed when `launcher.cpp`, `app.rc`, `app.manifest` or the icon
change. A normal patch touches none of them, so the exe is carried forward unchanged.
Apart from the PE build timestamp and its checksum - six bytes - the build reproduces.

Do not reintroduce port scanning or socket probing into the launcher, do not request
elevation (the manifest is `asInvoker` deliberately), and do not embed Python or the
panel into the exe.

## Version numbers

Three files must agree before building:

| file | field |
|---|---|
| `fleet-panel.py` | `APP_VERSION`, `APP_PATCH`, `APP_RELEASE_TAG` |
| `launcher-src/app.rc` | `FILEVERSION`, `PRODUCTVERSION`, and the two string values |
| `launcher-src/app.manifest` | `assemblyIdentity version=` |

`app.rc` and `app.manifest` are **LF-only, no BOM**. `APP_RELEASE_TAG` must equal the tag you
publish on GitHub, or the in-app update check reports the build as out of date.

Verify afterwards:

```
strings -a -el PandorumLLM.exe | grep 3.75.0.0
```

## Cutting a release

Run the gate on the staging copy first - it **blocks packaging**, and the packaging step
must check its exit code rather than merely run it:

```
python3 gate.py <staging-tree>
```

See `DEVELOPMENT.md` §7 for the full recipe and §8 for what the gate covers.
