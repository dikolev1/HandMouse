"""Screenshot-only precision restores the current base gain and respects the saved toggle."""
import os
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import hand_mouse as hm

class PrecisionTests(unittest.TestCase):
    def test_capture_restore_and_live_slider_changes(self):
        cursor = hm.CursorFilter((0,0,1920,1080),2)
        probe = Mock(side_effect=[True,True,False])
        precision = hm.ScreenshotPrecision(cursor,probe=probe)
        precision.update(1)
        self.assertEqual(cursor.sensitivity*cursor.gain_multiplier,1.5)
        cursor.sensitivity=1.2
        precision.update(1.3)
        self.assertAlmostEqual(cursor.sensitivity*cursor.gain_multiplier,.9)
        precision.update(1.6)
        self.assertEqual(cursor.sensitivity,1.2)
        self.assertEqual(cursor.gain_multiplier,1)

    def test_slow_cursor_displacement_is_reduced_by_a_quarter(self):
        normal=hm.CursorFilter((0,0,1920,1080),1)
        reduced=hm.CursorFilter((0,0,1920,1080),1)
        reduced.gain_multiplier=.75
        for k in range(120):
            normal(500+k*.2,500,k/30)
            reduced(500+k*.2,500,k/30)
        self.assertGreater(normal.cur[0],500)
        self.assertAlmostEqual(reduced.cur[0]-500,(normal.cur[0]-500)*.75,places=6)

    def test_disable_restores_immediately_and_stops_probe(self):
        cursor = hm.CursorFilter((0,0,100,100),.25)
        probe=Mock(return_value=True)
        precision=hm.ScreenshotPrecision(cursor,probe=probe)
        precision.update(1)
        self.assertEqual(cursor.sensitivity*cursor.gain_multiplier,.1875)
        precision.set_enabled(False)
        self.assertEqual(cursor.gain_multiplier,1)
        precision.update(2)
        probe.assert_called_once()
        precision.set_enabled(True)
        precision.update(2.01)
        self.assertEqual(cursor.gain_multiplier,.75)

    def test_poll_is_throttled_and_errors_restore(self):
        cursor=hm.CursorFilter((0,0,100,100))
        probe=Mock(side_effect=[True,OSError("unavailable")])
        precision=hm.ScreenshotPrecision(cursor,probe=probe)
        precision.update(1)
        precision.update(1.1)
        probe.assert_called_once()
        precision.update(1.3)
        self.assertEqual(cursor.gain_multiplier,1)

    def test_capture_overlay_and_editor_distinction(self):
        full=(0,0,1920,1080)
        small=(100,100,900,700)
        for process,cls,rect,topmost,want in [
            ("ScreenClippingHost.exe","Windows.UI.Core.CoreWindow",full,True,True),
            ("SnippingTool.exe","Microsoft-Windows-SnipperCaptureForm",small,True,True),
            ("SnippingTool.exe","Other",full,True,True),
            ("SnippingTool.exe","Other",full,False,False),
            ("SnippingTool.exe","Other",small,True,False),
            ("notepad.exe","Microsoft-Windows-SnipperCaptureForm",full,True,False),
            ("SnippingTool.exe","Other",(0,0,0,0),True,False)]:
            with self.subTest(process=process,cls=cls,rect=rect,topmost=topmost):
                self.assertEqual(hm.screenshot_window(process,cls,rect,full,topmost),want)

if __name__=="__main__":
    unittest.main()
