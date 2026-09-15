// ================================================================
//  PandorumLLM.exe - native launcher (v1.0 Beta)
//  Starts fleet-panel.py hidden, scans the panel port candidates until
//  one answers, and opens the browser there. Port logic lives in
//  fleet-panel.py; this exe just starts it and finds where it landed.
//  No elevation: the panel binds high ports and writes only inside its
//  own folder. --serve is kept as an alias for the same work.
// ================================================================
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <cstdio>

// The panel writes the port it settled on into panel-port.txt. Reading that file is
// how the .bat finds it too. This used to open sockets and probe five candidate ports
// instead - which works, but a small unsigned launcher doing port scans reads to an
// antivirus classifier as network reconnaissance. There is nothing here a text editor
// could not do now: read a file, start a program, open a browser.
static int ReadPortFile(const std::wstring& dir) {
    std::wstring path = dir + L"\\panel-port.txt";
    FILE* f = _wfopen(path.c_str(), L"rb");
    if (!f) return 0;
    char buf[32]; ZeroMemory(buf, sizeof(buf));
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    if (!n) return 0;
    int port = atoi(buf);
    return (port > 0 && port < 65536) ? port : 0;
}

static std::wstring ExeDir() {
    wchar_t p[MAX_PATH]; GetModuleFileNameW(NULL, p, MAX_PATH);
    std::wstring s(p);
    size_t k = s.find_last_of(L"\\/");
    return (k == std::wstring::npos) ? s : s.substr(0, k);
}

static bool FindOnPath(const wchar_t* name, std::wstring& out) {
    wchar_t buf[MAX_PATH];
    if (SearchPathW(NULL, name, NULL, MAX_PATH, buf, NULL)) { out = buf; return true; }
    return false;
}

static int Serve() {
    std::wstring py;
    // pythonw first: it has no console window at all, so the panel can be started with
    // ordinary creation flags. Asking for CREATE_NO_WINDOW instead means telling Windows
    // to hide a process, which is a thing worth avoiding in an unsigned binary.
    if (!FindOnPath(L"pythonw.exe", py)
        && !FindOnPath(L"py.exe", py) && !FindOnPath(L"python.exe", py)) {
        MessageBoxW(NULL, L"No Python (pythonw / py / python) found on PATH.",
                    L"PandorumLLM", MB_ICONERROR);
        return 1;
    }
    std::wstring dir = ExeDir();
    DeleteFileW((dir + L"\\panel-port.txt").c_str());   // never trust a stale one
    std::wstring script = dir + L"\\fleet-panel.py";
    if (GetFileAttributesW(script.c_str()) == INVALID_FILE_ATTRIBUTES) {
        std::wstring msg = L"fleet-panel.py not found next to the exe:\n" + script;
        MessageBoxW(NULL, msg.c_str(), L"PandorumLLM", MB_ICONERROR);
        return 1;
    }
    std::wstring cmd = L"\"" + py + L"\" \"" + script + L"\"";
    STARTUPINFOW si; ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    PROCESS_INFORMATION pi; ZeroMemory(&pi, sizeof(pi));
    std::wstring mcmd = cmd;
    DWORD flags = 0;
    if (py.find(L"pythonw.exe") == std::wstring::npos)
        flags = CREATE_NO_WINDOW;      // only the console builds need hiding
    if (!CreateProcessW(NULL, &mcmd[0], NULL, NULL, FALSE, flags,
                        NULL, dir.c_str(), &si, &pi)) {
        MessageBoxW(NULL, L"Failed to start the panel process.", L"PandorumLLM", MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return 0;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR cmdline, int) {
    if (cmdline && wcsstr(cmdline, L"--serve")) return Serve();

    // Start the panel directly. This used to relaunch the exe as administrator with
    // ShellExecuteExW("runas") and SW_HIDE - but the panel needs no administrator
    // rights (it binds high ports and writes only inside its own folder, and the
    // manifest has always said asInvoker), so the elevation was a leftover from an
    // older design. It also happened to be the most malware-shaped thing in this
    // binary: a program that silently relaunches itself elevated and hidden is what
    // droppers do, and Defender's ML classifier read it that way. One less UAC prompt
    // as well.
    if (Serve() != 0) return 1;

    Sleep(300);                             // python is usually up within a second
    std::wstring dir = ExeDir();
    int found = 0;
    for (int i = 0; i < 80 && !found; i++) {   // ~24 s ceiling, same as before
        found = ReadPortFile(dir);
        if (!found) Sleep(i < 12 ? 200 : 400);
    }
    if (found) {
        Sleep(250);
        wchar_t url[64];
        wsprintfW(url, L"http://localhost:%d/", found);
        ShellExecuteW(NULL, L"open", url, NULL, NULL, SW_SHOWNORMAL);
    } else {
        MessageBoxW(NULL,
            L"The panel did not report a port within 24 seconds -\n"
            L"it likely failed to start.\n\n"
            L"A stuck previous PandorumLLM is detected and closed automatically\n"
            L"at startup, so check for a crash instead:\n"
            L"  logs\\STARTUP-CRASH.log  (any startup failure lands here)\n"
            L"  logs\\PORTERROR.log      (only if ports were the problem)\n"
            L"  logs\\panel.log          (normal startup log)\n"
            L"  panel-port.txt          (the port actually chosen)\n"
            L"and that Python (py / python) is on PATH.",
            L"PandorumLLM", MB_ICONWARNING);
    }
    return 0;
}
