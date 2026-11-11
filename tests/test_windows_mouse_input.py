"""Native input layout, virtual desktop movement, button pairs and delivery failures."""
import ctypes
import os
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import hand_mouse as hm

class NativeMouse(unittest.TestCase):
    def setUp(self):
        self.mouse = hm.WinMouse.__new__(hm.WinMouse)
        self.mouse.Input = hm.windows_input_type()
        self.mouse.input_error_at = -1e9
        self.events = []
        def send(count, ptr, size):
            self.assertEqual(count, 1)
            self.assertEqual(size, ctypes.sizeof(self.mouse.Input))
            p = ctypes.cast(ptr,ctypes.POINTER(self.mouse.Input)).contents
            self.events.append((p.type,p.mi.dwFlags,p.mi.mouseData,p.mi.dx,p.mi.dy))
            return 1
        self.mouse.send_input = Mock(side_effect=send)
        self.mouse.u = Mock()
        metrics = {76:-1920,77:-1080,78:3840,79:2160}
        self.mouse.u.GetSystemMetrics.side_effect = metrics.__getitem__

    def test_native_abi(self):
        self.assertEqual(ctypes.sizeof(self.mouse.Input),40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)

    def test_movement_negative_origin_and_clamping(self):
        self.mouse.move(-1920,-1080)
        self.mouse.move(1919,1079)
        self.mouse.move(9000,-9000)
        self.assertEqual([e[3:] for e in self.events],[(0,0),(65535,65535),(65535,0)])
        self.assertTrue(all(e[0]==0 and e[1]==0xC001 for e in self.events))

    def test_drag_button_pair_and_signed_wheels(self):
        self.mouse.button("left",True)
        self.mouse.move(100,100)
        self.mouse.button("left",False)
        self.mouse.wheel(-120)
        self.mouse.hwheel(120)
        self.mouse.button("x2",True)
        self.assertEqual([e[1] for e in self.events],[2,0xC001,4,0x800,0x1000,0x80])
        self.assertEqual(self.events[3][2], 0xFFFFFF88)
        self.assertEqual(self.events[5][2],2)

    def test_rejection_logged_without_retry_or_duplicate_click(self):
        self.mouse.send_input = Mock(return_value=0)
        with self.assertLogs(hm.log,level="WARNING") as logs:
            self.assertFalse(self.mouse._send_mouse(2))
            self.assertFalse(self.mouse._send_mouse(4))
        self.assertEqual(len(logs.output),1)
        self.assertEqual(self.mouse.send_input.call_count,2)

if __name__ == "__main__":
    unittest.main()
