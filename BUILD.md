# Building PandorumLLM.exe

The exe is a small C++ launcher that starts `fleet-panel.py` and opens the browser. It is
**not** committed — it is built and attached to a Release. The panel itself needs no build
step; it is plain Python.

## What you need

MinGW-w64 (`x86_64-w64-mingw32-g++` and `x86_64-w64-mingw32-windres`).

- Debian/Ubuntu/WSL: `sudo apt-get install mingw-w64`
- Windows: MSYS2, then `pacman -S mingw-w64-x86_64-gcc`

## Build

```
cd launcher-src
x86_64-w64-mingw32-windres app.rc -O coff -o app.o
x86_64-w64-mingw32-g++ -O2 -municode -mwindows launcher.cpp app.o \
  -o ../PandorumLLM.exe -lws2_32 -static -static-libgcc -static-libstdc++
rm -f app.o
```

`-static` matters: without it the exe needs MinGW runtime DLLs the user will not have.

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
strings -a -el PandorumLLM.exe | grep 3.72.0.0
```

## Cutting a release

Run the gate on the staging copy first - it **blocks packaging**, and the packaging step
must check its exit code rather than merely run it:

```
python3 gate.py <staging-tree>
```

See `DEVELOPMENT.md` §7 for the full recipe and §8 for what the gate covers.
