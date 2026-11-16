"""Full-screen local TV: idle, preparation, camera/progress and session result."""
import ctypes
import ctypes.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from .tv_state import TVPresentation


def hdmi_connected():
    return any(p.read_text().strip() == 'connected' for p in Path('/sys/class/drm').glob('*HDMI*/status'))


def preview_connected():
    """Opt-in lab bypass: require an actual viewer on our headless output.

    The ordinary HDMI check always takes priority. This never enables a blind
    session merely because Xwayland happens to exist without a monitor.
    """
    if os.environ.get('SMART_REHAB_LAPTOP_PREVIEW') != '1':
        return False
    socket = str(Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) /
                 'smart-rehab-preview.sock')
    try:
        def query(command):
            return json.loads(subprocess.check_output(
                ['wayvncctl', '-j', '-S', socket, command], timeout=.7,
                stderr=subprocess.DEVNULL, text=True))
        clients = query('client-list')
        if not isinstance(clients, list) or not clients:
            return False
        outputs = query('output-list')
        return isinstance(outputs, list) and any(
            isinstance(o, dict) and o.get('captured') is True and
            str(o.get('name', '')).startswith(('NOOP-', 'HEADLESS-')) and
            isinstance(o.get('width'), (int, float)) and o['width'] > 0 and
            isinstance(o.get('height'), (int, float)) and o['height'] > 0
            for o in outputs)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return False


def display_available():
    return hdmi_connected() or preview_connected()


class RenderBudget:
    """Bound CPU composition work without changing capture or pose resolution."""
    def __init__(self):
        self.hot = False

    def temperature(self, value):
        if value is None:
            return
        if value >= 70:
            self.hot = True
        elif value <= 65:
            self.hot = False

    def size(self, screen):
        # The renderer scales this aspect-matched canvas to the native viewport.
        # Avoid processing a 1080p/4K canvas for a source webcam of 640x480.
        limit = (640, 360) if self.hot else (1280, 720)
        scale = min(1.0, limit[0] / screen[0], limit[1] / screen[1])
        return tuple(max(1, round(d * scale)) for d in screen)


class Display:
    def __init__(self, *, clock=time.monotonic):
        self.lock = threading.Lock()
        self.frame, self.received = None, 0.0
        self.ready = False
        self.clock = clock
        self.presentation = TVPresentation(clock())
        self.health = lambda: {}
        self.render_budget = RenderBudget()

    def set_temperature(self, temperature):
        with self.lock:
            self.render_budget.temperature(temperature)

    def canvas_size(self, screen):
        with self.lock:
            return self.render_budget.size(screen)

    def bind_health(self, provider):
        self.health = provider

    def begin(self, meta):
        with self.lock:
            self.frame = None
            self.presentation.begin(meta)

    def progress(self, sample, phase, countdown=None):
        with self.lock:
            self.presentation.progress(sample, phase, countdown)

    def stopping(self):
        with self.lock:
            self.presentation.mode = 'stopping'
            self.presentation.countdown = None

    def finish(self, summary):
        with self.lock:
            self.frame = None
            self.presentation.finish(summary, self.clock())

    def snapshot(self):
        # Never acquire the hub lock while holding the display lock.
        health, now = self.health(), self.clock()
        with self.lock:
            active = self.presentation.mode not in ('idle', 'summary')
            frame = self.frame if active and now-self.received < 1 else None
            view = self.presentation.view(now, health, frame is not None)
            return view, frame, self.received if frame is not None else 0

    def offer(self, frame):
        with self.lock:
            self.frame, self.received = frame, self.clock()

    def blank(self):
        with self.lock:
            self.frame = None

    def run(self, stop):
        os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
        x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
        fixes = ctypes.CDLL(ctypes.util.find_library('Xfixes'))
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XGetGeometry.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        for fn in (fixes.XFixesHideCursor, fixes.XFixesShowCursor):
            fn.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        # HDMI can be present before labwc/Xwayland is ready at boot. Qt aborts
        # the process if opened too early; keep BLE/cloud available while waiting.
        connection = None
        while not stop.is_set():
            if display_available():
                connection = x11.XOpenDisplay(None)
                if connection:
                    break
            stop.wait(.5)
        if stop.is_set():
            if connection:
                x11.XCloseDisplay(connection)
            return
        import cv2
        from .tv_renderer import TVRenderer
        renderer = TVRenderer()
        # OpenCV/Qt window and waitKey must run on the main graphical thread.
        name = 'SMART REHAB'
        root_window = x11.XDefaultRootWindow(connection)
        def screen_size():
            root = ctypes.c_ulong()
            x, y = ctypes.c_int(), ctypes.c_int()
            width, height, border, depth = (ctypes.c_uint() for _ in range(4))
            ok = x11.XGetGeometry(connection, root_window, ctypes.byref(root), ctypes.byref(x), ctypes.byref(y),
                                 ctypes.byref(width), ctypes.byref(height), ctypes.byref(border), ctypes.byref(depth))
            return (width.value, height.value) if ok and width.value and height.value else (1280, 720)
        native_size = screen_size()
        size = self.canvas_size(native_size)
        # Supply a complete aspect-matched canvas with explicit source fit.
        # Explicitly expand it to the native viewport; only composition is capped.
        cv2.namedWindow(name, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO | cv2.WINDOW_GUI_NORMAL)
        cv2.resizeWindow(name, *native_size)
        view, _, _ = self.snapshot()
        cv2.imshow(name, renderer.render_for_screen(native_size, size, view))
        cv2.waitKey(1)
        cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        # XFixes hides the cursor for this X connection and restores it on exit.
        if connection:
            fixes.XFixesHideCursor(connection, x11.XDefaultRootWindow(connection))
            x11.XFlush(connection)
        rendered = None
        last_connector_check = 0.0
        try:
            while not stop.is_set():
                now = time.monotonic()
                if now - last_connector_check >= 1:
                    self.ready = display_available()
                    new_native = screen_size()
                    new_size = self.canvas_size(new_native)
                    if new_native != native_size:
                        native_size = new_native
                        cv2.resizeWindow(name, *native_size)
                        cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    if new_size != size:
                        size = new_size
                        rendered = None
                    last_connector_check = now
                view, frame, stamp = self.snapshot()
                signature = (stamp, view)
                if signature != rendered:
                    cv2.imshow(name, renderer.render_for_screen(native_size, size, view, frame))
                    rendered = signature
                cv2.waitKey(30 if frame is not None else 100)
        finally:
            self.ready = False
            if connection:
                fixes.XFixesShowCursor(connection, x11.XDefaultRootWindow(connection))
                x11.XFlush(connection)
                x11.XCloseDisplay(connection)
            cv2.destroyAllWindows()
