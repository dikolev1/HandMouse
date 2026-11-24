"""Experimental cursor appearance and gesture hold feedback on Windows."""
import ctypes as c
from ctypes import wintypes as w
import logging
import math
import sys
import threading
import time

log = logging.getLogger("hand_mouse")


FEEDBACK_OPTIONS = {
    "mirror": "Mirror the Windows arrow for the left main hand",
    "close_ring": "Close window countdown ring",
    "close_shake": "Shake the pointer during Close window",
    "camera_ring": "Camera & log countdown ring",
    "enable_ring": "Turn gestures on countdown and result",
    "disable_ring": "Turn gestures off countdown and result",
    "squeeze": "Squeeze animation when a gesture activates",
}

COLORS = {
    "red": ("#ff4646", "#812d36"),
    "blue": ("#459eff", "#25446b"),
    "yellow": ("#ffd447", "#77632c"),
    "green": ("#44e688", "#276643"),
}


class GestureSwitchFeedback:
    """Read the existing on/off timers without changing recognition."""
    def __init__(self):
        self.wake_armed = False
        self.result = None

    def update(self, engine, now, visible_pair, prefs, stop_hold):
        wake = engine.wake
        armed = engine.gestures_off and (
            (wake.phase == "hold" and wake.ready) or wake.phase in ("opening", "release"))
        changed = engine.gestures_changed
        source = getattr(engine, "gestures_change_source", None)
        result = None
        if changed == "on" and source == "fists 1-3 s / open palms 1 s":
            result = ("enable_ring", "green")
        elif changed == "off" and source == "two fists":
            result = ("disable_ring", "red")
        elif engine.gestures_off and (wake.feedback == "overheld" or (self.wake_armed and not armed)):
            result = ("enable_ring", "red")
        self.wake_armed = armed
        if result:
            self.result = (*result, now + 0.2)
        if self.result:
            option, color, deadline = self.result
            if now < deadline and prefs[option]:
                return color, 1.0
            if now >= deadline:
                self.result = None
        if armed and prefs["enable_ring"]:
            if wake.phase == "hold":
                fraction = (now - wake.since - 1) / 2
            elif wake.phase == "opening":
                fraction = 1 - (wake.deadline - now) / 0.7
            else:
                fraction = 0 if wake.since is None else now - wake.since
            return "yellow", max(0.0, min(1.0, fraction))
        if visible_pair and engine.both_fists_since is not None and prefs["disable_ring"]:
            return "yellow", min(1.0, (now - engine.both_fists_since) / stop_hold)
        return None


def api(dll, name, result, *args):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function


class IconInfo(c.Structure):
    _fields_ = [("icon", w.BOOL), ("x", w.DWORD), ("y", w.DWORD),
                ("mask", w.HANDLE), ("color", w.HANDLE)]


class Bitmap(c.Structure):
    _fields_ = [("kind", w.LONG), ("width", w.LONG), ("height", w.LONG),
                ("stride", w.LONG), ("planes", w.WORD), ("bits", w.WORD),
                ("data", c.c_void_p)]


def mirror_rows(data, width, height, stride, depth):
    output = bytearray(data)
    for y in range(height):
        start = y * stride
        row = data[start:start + stride]
        if depth == 1:
            for x in range(width):
                source = width - 1 - x
                bit = (row[source // 8] >> (7 - source % 8)) & 1
                index, flag = start + x // 8, 128 >> (x % 8)
                output[index] = (output[index] & ~flag) | (flag if bit else 0)
        elif depth in (8, 16, 24, 32):
            size = depth // 8
            output[start:start + width * size] = b"".join(
                row[x:x + size] for x in range((width - 1) * size, -1, -size))
        else:
            raise ValueError(f"Unsupported cursor bitmap depth {depth}")
    return bytes(output)


class WindowsPointer:
    NORMAL = 32512

    def __init__(self):
        self.user = c.WinDLL("user32", use_last_error=True)
        self.gdi = c.WinDLL("gdi32", use_last_error=True)
        u, g = self.user, self.gdi
        self.load = api(u, "LoadCursorW", w.HANDLE, w.HINSTANCE, c.c_void_p)
        self.copy = api(u, "CopyIcon", w.HANDLE, w.HANDLE)
        self.destroy = api(u, "DestroyCursor", w.BOOL, w.HANDLE)
        self.replace = api(u, "SetSystemCursor", w.BOOL, w.HANDLE, w.DWORD)
        self.info = api(u, "GetIconInfo", w.BOOL, w.HANDLE, c.POINTER(IconInfo))
        self.create = api(u, "CreateIconIndirect", w.HANDLE, c.POINTER(IconInfo))
        self.describe = api(g, "GetObjectW", c.c_int, w.HANDLE, c.c_int, c.c_void_p)
        self.read = api(g, "GetBitmapBits", w.LONG, w.HANDLE, w.LONG, c.c_void_p)
        self.write = api(g, "SetBitmapBits", w.LONG, w.HANDLE, w.DWORD, c.c_void_p)
        self.delete = api(g, "DeleteObject", w.BOOL, w.HANDLE)
        self.original = None

    def mirror(self, cursor):
        info = IconInfo()
        if not self.info(cursor, c.byref(info)):
            raise c.WinError(c.get_last_error())
        try:
            width = 0
            for handle in (info.mask, info.color):
                if not handle:
                    continue
                bitmap = Bitmap()
                if not self.describe(handle, c.sizeof(bitmap), c.byref(bitmap)):
                    raise c.WinError(c.get_last_error())
                width = bitmap.width
                length = bitmap.stride * bitmap.height
                buffer = c.create_string_buffer(length)
                if self.read(handle, length, buffer) != length:
                    raise OSError("Could not read cursor bitmap")
                reflected = mirror_rows(buffer.raw, width, bitmap.height, bitmap.stride, bitmap.bits)
                if self.write(handle, length, c.create_string_buffer(reflected)) != length:
                    raise OSError("Could not write cursor bitmap")
            info.x = width - 1 - info.x
            info.icon = False
            return self.create(c.byref(info))
        finally:
            for handle in (info.mask, info.color):
                if handle:
                    self.delete(handle)

    def update(self, left):
        if left and self.original is None:
            source = self.load(None, self.NORMAL)
            saved = self.copy(source)
            if not saved:
                raise c.WinError(c.get_last_error())
            try:
                mirrored = self.mirror(source)
                if not mirrored or not self.replace(mirrored, self.NORMAL):
                    raise c.WinError(c.get_last_error())
            except Exception:
                self.destroy(saved)
                raise
            self.original = saved
        elif not left and self.original is not None:
            saved, self.original = self.original, None
            if not self.replace(saved, self.NORMAL):
                self.user.SystemParametersInfoW(0x0057, 0, None, 0)


class CursorFeedback:
    def __init__(self):
        self.state = (None, 0.0, 0.0, False, False)
        self.pulse_at = -math.inf
        self.squeeze_enabled = True
        self.stop = threading.Event()
        self.thread = None
        self.pointer = None
        self.left = False

    def set_hand(self, side):
        left = side == "left"
        if sys.platform != "win32" or left == self.left:
            return
        self.left = left
        try:
            if self.pointer is None:
                self.pointer = WindowsPointer()
            self.pointer.update(left)
        except Exception:
            log.exception("Could not change cursor orientation")

    def show(self, color=None, fraction=0.0, shake=False, latch=False):
        self.state = (color, fraction, time.monotonic(), shake, latch)
        if color or shake:
            self._start()

    def squeeze(self):
        if self.squeeze_enabled:
            self.pulse_at = time.monotonic()
            self._start()

    def _start(self):
        if self.thread is None and sys.platform == "win32":
            self.thread = threading.Thread(target=self._run, daemon=True, name="cursor-feedback")
            self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        self.set_hand("right")

    def _run(self):
        try:
            self._overlay()
        except Exception:
            log.exception("Cursor feedback overlay failed")

    def _overlay(self):
        import struct
        from PIL import Image, ImageDraw

        u, g = c.WinDLL("user32"), c.WinDLL("gdi32")
        api(u, "SetThreadDpiAwarenessContext", c.c_void_p, c.c_void_p)(-4)
        get_pos = api(u, "GetCursorPos", w.BOOL, c.POINTER(w.POINT))
        set_pos = api(u, "SetCursorPos", w.BOOL, c.c_int, c.c_int)
        create = api(u, "CreateWindowExW", w.HANDLE, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                     c.c_int, c.c_int, c.c_int, c.c_int, w.HANDLE, w.HANDLE, w.HANDLE, c.c_void_p)
        show = api(u, "ShowWindow", w.BOOL, w.HANDLE, c.c_int)
        destroy = api(u, "DestroyWindow", w.BOOL, w.HANDLE)
        update = api(u, "UpdateLayeredWindow", w.BOOL, w.HANDLE, w.HDC, c.POINTER(w.POINT),
                     c.POINTER(w.SIZE), w.HDC, c.POINTER(w.POINT), w.DWORD, c.c_void_p, w.DWORD)
        new_dc = api(g, "CreateCompatibleDC", w.HDC, w.HDC)
        new_bitmap = api(g, "CreateDIBSection", w.HANDLE, w.HDC, c.c_void_p, w.UINT,
                         c.POINTER(c.c_void_p), w.HANDLE, w.DWORD)
        select = api(g, "SelectObject", w.HANDLE, w.HDC, w.HANDLE)
        delete_bitmap = api(g, "DeleteObject", w.BOOL, w.HANDLE)
        delete_dc = api(g, "DeleteDC", w.BOOL, w.HDC)
        peek = api(u, "PeekMessageW", w.BOOL, c.POINTER(w.MSG), w.HANDLE, w.UINT, w.UINT, w.UINT)
        dispatch = api(u, "DispatchMessageW", c.c_ssize_t, c.POINTER(w.MSG))

        edge = 50
        # Layered, click-through, topmost, tool window, and no activation.
        hwnd = create(0x080800A8, "Static", "Hand Mouse gesture feedback", 0x80000000,
                      0, 0, edge, edge, None, None, None, None)
        if not hwnd:
            raise OSError("Could not create cursor feedback window")
        dc = new_dc(None)
        bitmap = old_bitmap = None
        visible = False
        shifted = base = None
        completion_until = 0.0
        completion_stamp = completion_color = None
        try:
            header = c.create_string_buffer(struct.pack(
                "<IiiHHIIiiII", 40, edge, -edge, 1, 32, 0, 0, 0, 0, 0, 0))
            pixels = c.c_void_p()
            bitmap = new_bitmap(dc, header, 0, c.byref(pixels), None, 0)
            if not bitmap:
                raise OSError("Could not allocate cursor feedback bitmap")
            old_bitmap = select(dc, bitmap)
            blend = c.create_string_buffer(bytes((0, 0, 255, 1)))
            size, origin, point, message = w.SIZE(edge, edge), w.POINT(), w.POINT(), w.MSG()
            rendered = None

            while not self.stop.is_set():
                while peek(c.byref(message), None, 0, 0, 1):
                    dispatch(c.byref(message))
                get_pos(c.byref(point))
                current = (point.x, point.y)
                color, fraction, stamp, shake, latch = self.state
                now = time.monotonic()
                if color and latch and fraction == 1 and stamp != completion_stamp:
                    completion_stamp, completion_color = stamp, color
                    completion_until = now + 0.12
                if now - stamp > 0.35:
                    color, shake = None, False
                elif not color and now < completion_until:
                    color, fraction = completion_color, 1.0
                if shifted is not None and current == shifted:
                    current = base
                elif shifted is not None:
                    shifted = base = None
                pulse_age = now - self.pulse_at
                pulse = self.squeeze_enabled and 0 <= pulse_age < 0.16
                inset = round(5 * math.sin(math.pi * pulse_age / 0.16)) if pulse else 0
                if color or shake or pulse:
                    x, y = current
                    offset = round(2 * math.sin(now * 44)) if shake and fraction < 1 else 0
                    if offset or shifted is not None:
                        target = (x + offset, y)
                        if target != (point.x, point.y):
                            set_pos(*target)
                        base, shifted = (current, target) if offset else (None, None)
                    drawing = (color, fraction, inset, pulse)
                    if rendered != drawing:
                        picture = Image.new("RGBA", (edge, edge))
                        draw = ImageDraw.Draw(picture)
                        bounds = (5 + inset, 5 + inset, 45 - inset, 45 - inset)
                        if color:
                            accent, track = COLORS[color]
                            draw.ellipse(bounds, outline=track, width=3)
                            if fraction >= 1:
                                draw.ellipse(bounds, outline=accent, width=4)
                            elif fraction > 0:
                                draw.arc(bounds, -90, -90 + 360 * fraction, fill=accent, width=4)
                        elif pulse:
                            draw.ellipse(bounds, outline="#233449", width=3)
                            draw.ellipse(bounds, outline="#e8f3ff", width=1)
                        c.memmove(pixels, picture.tobytes("raw", "BGRA"), edge * edge * 4)
                        rendered = drawing
                    position = w.POINT(x - edge // 2, y - edge // 2)
                    update(hwnd, None, c.byref(position), c.byref(size), dc, c.byref(origin), 0, blend, 2)
                    if not visible:
                        show(hwnd, 4)  # SW_SHOWNOACTIVATE
                        visible = True
                else:
                    if shifted is not None:
                        set_pos(*base)
                        shifted = base = None
                    if visible:
                        show(hwnd, 0)
                        visible = False
                self.stop.wait(0.016 if visible else 0.05)
        finally:
            if shifted is not None and get_pos(c.byref(point)) and (point.x, point.y) == shifted:
                set_pos(*base)
            if old_bitmap:
                select(dc, old_bitmap)
            if bitmap:
                delete_bitmap(bitmap)
            if dc:
                delete_dc(dc)
            destroy(hwnd)
