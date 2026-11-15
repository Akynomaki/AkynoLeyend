/* The game's window (Windows): the renderer's surface (gpu/render/, WebGPU). The native NVN layer (nvn_native.c)
   presents the game's window textures into it (rx_nvn_present). The title bar carries live numbers.
   TOTKPort's hos/display.c, without its emulated-GPU fallback (the window buffer read from guest memory): MKW has
   no emulated GPU, so the renderer is the only way to a picture.
   HOS_HEADLESS=1: no window (scripted runs; the renderer draws offscreen). Closing the window ends the run.
   HOS_WINDOW_NOACTIVATE=1: the window opens behind the one in front (test runs do not take the keyboard).
   HOS_WINDOW_SIZE=<w>x<h>: the client area (default 1280x720 at 96 dpi). F11: fullscreen.
   Mouse: a click in the window captures the mouse (hidden, kept in the window), Esc or leaving the window releases
   it (nn_hid.c reads its motion). */
#include "hos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "../gpu/render/rx.h"
#ifndef WM_DPICHANGED
#define WM_DPICHANGED 0x02E0
#endif

volatile LONG64 hos_present_count;   /* (nvn_native.c: the game's presents) */
static HWND hwnd;
static int renderer;   /* the renderer presents into the window */

/* mouse capture: raw motion accumulated here, taken by nn_hid.c */
static volatile LONG mouse_dx, mouse_dy;
static volatile LONG mouse_captured;
static int cursor_hidden;
static int menu_open, menu_restore_capture;

int hos_mouse_take(int32_t *dx, int32_t *dy) {
    *dx = InterlockedExchange(&mouse_dx, 0);
    *dy = InterlockedExchange(&mouse_dy, 0);
    return mouse_captured;
}

/* (AkynoLeyend r13, Hookshot v2.1.0: mouse_native.c) motion taken and not used, put back for the next taker (the player
   camera's) */
void hos_mouse_give_back(int32_t dx, int32_t dy) {
    InterlockedExchangeAdd(&mouse_dx, dx);
    InterlockedExchangeAdd(&mouse_dy, dy);
}

static HANDLE renderer_up;
static int fullscreen;
static WINDOWPLACEMENT windowed_place;

static void set_fullscreen(HWND w, int on) {
    if (on == fullscreen) return;
    const LONG style = GetWindowLongA(w, GWL_STYLE);
    if (on) {
        MONITORINFO mi;
        mi.cbSize = sizeof mi;
        windowed_place.length = sizeof windowed_place;
        if (!GetWindowPlacement(w, &windowed_place) ||
            !GetMonitorInfoA(MonitorFromWindow(w, MONITOR_DEFAULTTONEAREST), &mi))
            return;
        fullscreen = 1;
        SetWindowLongA(w, GWL_STYLE, style & ~WS_OVERLAPPEDWINDOW);
        SetWindowPos(w, HWND_TOP, mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right - mi.rcMonitor.left,
                     mi.rcMonitor.bottom - mi.rcMonitor.top, SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
    } else {
        fullscreen = 0;
        SetWindowLongA(w, GWL_STYLE, style | WS_OVERLAPPEDWINDOW);
        SetWindowPlacement(w, &windowed_place);
        SetWindowPos(w, NULL, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
    }
    hos_log("display: %s", on ? "fullscreen (F11 for a window)" : "windowed");
}

static void dpi_aware_thread(void) {
    if (getenv("HOS_DPI_UNAWARE")) return;
    typedef void *(WINAPI * SetCtx)(void *);
    SetCtx set = (SetCtx)(void *)GetProcAddress(GetModuleHandleA("user32.dll"), "SetThreadDpiAwarenessContext");
    if (set) set((void *)(intptr_t)-4);
}

static UINT window_dpi(HWND w) {
    typedef UINT(WINAPI * GetDpi)(HWND);
    GetDpi get = (GetDpi)(void *)GetProcAddress(GetModuleHandleA("user32.dll"), "GetDpiForWindow");
    const UINT dpi = get ? get(w) : 96;
    return dpi ? dpi : 96;
}

static void mouse_capture(HWND w, int on) {
    if (on == (int)mouse_captured) return;
    mouse_captured = on;
    InterlockedExchange(&mouse_dx, 0);
    InterlockedExchange(&mouse_dy, 0);
    if (on) {
        RECT rc;
        GetClientRect(w, &rc);
        MapWindowPoints(w, NULL, (POINT *)&rc, 2);
        ClipCursor(&rc);
        if (!cursor_hidden) { ShowCursor(FALSE); cursor_hidden = 1; }
    } else {
        ClipCursor(NULL);
        if (cursor_hidden) { ShowCursor(TRUE); cursor_hidden = 0; }
    }
}

/* The window was closed: the GPU's last work finished and NVIDIA DLSS shut down (rx_before_exit), then the process ends.
   ExitProcess straight from WM_CLOSE, with DLSS on, faulted the GPU at the close (nvlddmkm 153, a TDR the driver did not
   recover from) */
static DWORD WINAPI close_main(void *p) {
    (void)p;
    rx_before_exit();
    hos_log_flush();
    ExitProcess(0);
}

static LRESULT CALLBACK wndproc(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_TIMER:
        return 0;
    case WM_INPUT: {
        RAWINPUT ri;
        UINT size = sizeof ri;
        if (mouse_captured && GetRawInputData((HRAWINPUT)lp, RID_INPUT, &ri, &size, sizeof(RAWINPUTHEADER)) != (UINT)-1 &&
            ri.header.dwType == RIM_TYPEMOUSE && !(ri.data.mouse.usFlags & MOUSE_MOVE_ABSOLUTE)) {
            InterlockedExchangeAdd(&mouse_dx, ri.data.mouse.lLastX);
            InterlockedExchangeAdd(&mouse_dy, ri.data.mouse.lLastY);
        }
        return DefWindowProcA(w, msg, wp, lp);
    }
    case WM_LBUTTONDOWN:
        if (renderer && !menu_open && !mouse_captured) mouse_capture(w, 1);
        return 0;
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE) mouse_capture(w, 0);
        if (wp == VK_F11 && !(lp & (1 << 30))) set_fullscreen(w, !fullscreen);
        return 0;
    case WM_APP + 7:   /* (the Insert menu's row) */
        set_fullscreen(w, (int)wp);
        return 0;
    case WM_APP + 8:   /* Options release the pointer; a click there must not capture it. */
        if (wp && !menu_open) { menu_restore_capture = mouse_captured; mouse_capture(w, 0); }
        menu_open = wp != 0;
        if (!menu_open && menu_restore_capture) {
            menu_restore_capture = 0;
            if (GetForegroundWindow() == w) mouse_capture(w, 1);
        }
        return 0;
    case WM_DPICHANGED:
        if (!fullscreen) {
            const RECT *s = (const RECT *)lp;
            SetWindowPos(w, NULL, s->left, s->top, s->right - s->left, s->bottom - s->top,
                         SWP_NOZORDER | SWP_NOACTIVATE);
        }
        return 0;
    case WM_KILLFOCUS:
    case WM_CANCELMODE:
        menu_restore_capture = 0;
        mouse_capture(w, 0);
        break;
    case WM_SETCURSOR:
        if (mouse_captured && LOWORD(lp) == HTCLIENT) {
            SetCursor(NULL);
            return TRUE;
        }
        break;
    case WM_MOVE:
        if (mouse_captured) { mouse_capture(w, 0); mouse_capture(w, 1); }   /* (the clip follows the window) */
        break;
    case WM_SIZE:
        if (mouse_captured) { mouse_capture(w, 0); mouse_capture(w, 1); }
        if (renderer) rx_resize(LOWORD(lp), HIWORD(lp));
        return 0;
    case WM_PAINT:
        if (renderer) {   /* the renderer's surface: nothing to paint */
            ValidateRect(w, NULL);
            return 0;
        }
        break;
    case WM_ERASEBKGND:
        return renderer ? 1 : DefWindowProcA(w, msg, wp, lp);
    case WM_CLOSE: {
        /* (the renderer's end on a thread of its own: this one goes on with the window's messages, which a present under
           way may wait for. A second close does not wait) */
        static volatile LONG closing;
        hos_log("display: window closed, exiting");
        hos_log_flush();
        if (InterlockedExchange(&closing, 1) || !CreateThread(NULL, 0, close_main, NULL, 0, NULL)) ExitProcess(0);
        return 0;
    }
    }
    return DefWindowProcA(w, msg, wp, lp);
}

static DWORD WINAPI display_main(void *p) {
    (void)p;
    {   /* (nothing is typed here. Windows' text services, set up under DefWindowProc as the window was sized, ended the process: a
           fail-fast in CoreMessaging, called from textinputframework) */
        HMODULE imm = LoadLibraryA("imm32.dll");
        BOOL (WINAPI *ime_off)(DWORD) = imm ? (BOOL (WINAPI *)(DWORD))GetProcAddress(imm, "ImmDisableIME") : NULL;
        if (ime_off) ime_off((DWORD)-1);
    }
    WNDCLASSA wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wndproc;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hIcon = LoadIconA(wc.hInstance, MAKEINTRESOURCEA(1));   /* (nx2/make_icon.py; none in a build without the picture) */
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    wc.lpszClassName = "AkynoLeyend";
    RegisterClassA(&wc);
    dpi_aware_thread();
    extern float hos_aspect_ratio;
    int hos_output_mode(void);
    const float aspect = hos_output_mode() == 5 ? 2560.0f / 1600.0f :
                         hos_aspect_ratio > 1.8f ? hos_aspect_ratio : 16.0f / 9.0f;
    int win_w = (int)(720 * aspect + 0.5f), win_h = 720;
    int exact_pixels = 0;
    const char *window_size = getenv("HOS_WINDOW_SIZE");
    if (window_size) {
        int w = 0, h = 0;
        if (sscanf(window_size, "%dx%d", &w, &h) == 2 && w >= 64 && h >= 64) {
            win_w = w;
            win_h = h;
            exact_pixels = 1;
        }
    }
    RECT r = {0, 0, win_w, win_h};
    AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW, FALSE);
    const int noactivate = getenv("HOS_WINDOW_NOACTIVATE") != NULL;
    hwnd = CreateWindowA("AkynoLeyend", HOS_GAME_TITLE, WS_OVERLAPPEDWINDOW, CW_USEDEFAULT,
                         CW_USEDEFAULT, r.right - r.left, r.bottom - r.top, NULL, NULL, wc.hInstance, NULL);
    if (!exact_pixels && window_dpi(hwnd) != 96) {
        const UINT dpi = window_dpi(hwnd);
        RECT s = {0, 0, (LONG)(win_w * dpi / 96), (LONG)(win_h * dpi / 96)};
        AdjustWindowRect(&s, WS_OVERLAPPEDWINDOW, FALSE);
        SetWindowPos(hwnd, NULL, 0, 0, s.right - s.left, s.bottom - s.top, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    }
    /* (no activate: shown at the bottom of the z-order, so a game in front keeps its focus) */
    if (noactivate)
        SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
    else
        ShowWindow(hwnd, SW_SHOW);
    if (getenv("HOS_FULLSCREEN") && atoi(getenv("HOS_FULLSCREEN"))) set_fullscreen(hwnd, 1);
    RAWINPUTDEVICE rid = {1, 2, 0, hwnd};   /* generic desktop mouse: WM_INPUT while the window is in front */
    RegisterRawInputDevices(&rid, 1, sizeof rid);
    renderer = rx_start(hwnd);
    if (!renderer) hos_fatal(NULL, "display: could not start the Vulkan renderer");
    SetEvent(renderer_up);
    SetTimer(hwnd, 1, 250, NULL);
    MSG m;
    while (GetMessageA(&m, NULL, 0, 0) > 0) {
        TranslateMessage(&m);
        DispatchMessageA(&m);
    }
    return 0;
}

/* (hookshot) The game's first work for the GPU waits for the renderer. It ran beside the renderer's start, and what it submitted while the
   shaders were being prepared (80 s on a first start) was lost: that run had no ambient light, black foliage and dark characters. The
   game itself goes on starting as it did: held at the start instead, it left holes in the ground */
void hos_renderer_wait(void) {
    { const char *e = getenv("HOS_NO_RENDERER_WAIT"); if (e && atoi(e) != 0) return; }   /* (=0: the wait, as without it) */   /* (a test: the game's first GPU work no longer waits for the renderer, as before lighting-fix) */
    if (renderer_up && WaitForSingleObject(renderer_up, INFINITE) != WAIT_OBJECT_0)
        hos_fatal(NULL, "display: failed while waiting for the Vulkan renderer");
}

void hos_display_start(void) {
    if (getenv("HOS_HEADLESS")) {   /* no window: the renderer still draws, offscreen (screenshots, frame dumps) */
        rx_start(NULL);
        return;
    }
    renderer_up = CreateEventA(NULL, TRUE, FALSE, NULL);
    if (!renderer_up) hos_fatal(NULL, "display: could not create renderer startup event");
    HANDLE thread = CreateThread(NULL, 0, display_main, NULL, 0, NULL);
    if (!thread) hos_fatal(NULL, "display: could not start renderer thread");
    CloseHandle(thread);
}
