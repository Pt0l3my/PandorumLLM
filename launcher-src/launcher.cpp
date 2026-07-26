// ================================================================
//  PandorumLLM.exe - native launcher (v0.9 Beta)
//  Unelevated: relaunch self elevated with --serve (one UAC), then
//  scan the panel port candidates until one answers and open the
//  browser there (unelevated). Port logic lives in fleet-panel.py;
//  this exe just starts it and finds where it landed.
//  --serve (elevated): start fleet-panel.py hidden via py/python.
// ================================================================
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <shellapi.h>
#include <string>

static const int CANDS[] = {50607, 50617, 50627, 50637, 50647};
static const int NCANDS  = 5;

static bool PortOpen(int port) {
    SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
    if (s == INVALID_SOCKET) return false;
    sockaddr_in a; ZeroMemory(&a, sizeof(a));
    a.sin_family = AF_INET; a.sin_port = htons((u_short)port);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    u_long nb = 1; ioctlsocket(s, FIONBIO, &nb);
    connect(s, (sockaddr*)&a, sizeof(a));
    fd_set w; FD_ZERO(&w); FD_SET(s, &w);
    timeval tv; tv.tv_sec = 0; tv.tv_usec = 350 * 1000;
    bool ok = (select(0, NULL, &w, NULL, &tv) == 1);
    if (ok) {
        int err = 0; int len = sizeof(err);
        getsockopt(s, SOL_SOCKET, SO_ERROR, (char*)&err, &len);
        ok = (err == 0);
    }
    closesocket(s);
    return ok;
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
    if (!FindOnPath(L"py.exe", py) && !FindOnPath(L"python.exe", py)) {
        MessageBoxW(NULL, L"No Python (py / python) found on PATH.", L"PandorumLLM", MB_ICONERROR);
        return 1;
    }
    std::wstring dir = ExeDir();
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
    if (!CreateProcessW(NULL, &mcmd[0], NULL, NULL, FALSE, CREATE_NO_WINDOW,
                        NULL, dir.c_str(), &si, &pi)) {
        MessageBoxW(NULL, L"Failed to start the panel process.", L"PandorumLLM", MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return 0;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR cmdline, int) {
    WSADATA w; WSAStartup(MAKEWORD(2, 2), &w);
    if (cmdline && wcsstr(cmdline, L"--serve")) return Serve();

    wchar_t self[MAX_PATH]; GetModuleFileNameW(NULL, self, MAX_PATH);
    SHELLEXECUTEINFOW sei; ZeroMemory(&sei, sizeof(sei)); sei.cbSize = sizeof(sei);
    sei.lpVerb = L"runas"; sei.lpFile = self; sei.lpParameters = L"--serve";
    sei.nShow = SW_HIDE; sei.fMask = SEE_MASK_NOASYNC;
    if (!ShellExecuteExW(&sei)) return 1;   // UAC declined

    Sleep(300);                             // python is usually up within a second
    int found = 0;
    for (int i = 0; i < 80 && !found; i++) {   // fast poll, ~24 s ceiling
        for (int c = 0; c < NCANDS; c++) {
            if (PortOpen(CANDS[c])) { found = CANDS[c]; break; }
        }
        if (!found) Sleep(i < 12 ? 200 : 400);
    }
    if (found) {
        Sleep(250);
        wchar_t url[64];
        wsprintfW(url, L"http://localhost:%d/", found);
        ShellExecuteW(NULL, L"open", url, NULL, NULL, SW_SHOWNORMAL);
    } else {
        MessageBoxW(NULL,
            L"The panel didn't ANSWER on any of its ports\n"
            L"(50607, 50617, 50627, 50637, 50647) - it likely failed to start.\n\n"
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
