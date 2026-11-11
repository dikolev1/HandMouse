"""Camera selection persists, clears stale calibration and reaches the capture backend."""
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import hand_mouse as hm

class CameraChoice(unittest.TestCase):
    def test_persist_and_invalidate_old_camera_profile(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hm, "STATE_PATH", os.path.join(folder,"state.json")):
            hm.save_state(camera={"backend":"dshow"}, ref_palm=.1, cursor_sensitivity=1.5)
            hm.choose_camera(2)
            state = hm.load_state()
            self.assertEqual(hm.selected_camera(state), 2)
            self.assertIsNone(state["camera"])
            self.assertIsNone(state["ref_palm"])
            self.assertEqual(state["cursor_sensitivity"],1.5)

    def test_bad_values_fall_back_and_selection_rejects_them(self):
        for bad in (-1, 10, True, "2", None):
            self.assertEqual(hm.selected_camera({"camera_index":bad}), hm.CAMERA_INDEX)
            with self.assertRaises(ValueError):
                hm.choose_camera(bad)

    def test_capture_opens_selected_index(self):
        cv = Mock()
        cap = cv.VideoCapture.return_value
        cap.isOpened.return_value = True
        self.assertIs(hm._open_capture(cv, 700, 640, 480, 3),cap)
        cv.VideoCapture.assert_called_once_with(3,700)

    def test_resume_uses_matching_saved_profile_and_selected_camera(self):
        cv = Mock(CAP_DSHOW=700, CAP_MSMF=1400)
        capture = Mock()
        with patch.object(hm, "_open_capture", return_value=capture) as opened, patch.object(hm,"Camera") as camera:
            hm.open_camera(cv, {"camera_index":4,"camera":{"index":4,"backend":"dshow","w":640,"h":480}},verify=False)
            opened.assert_called_once_with(cv,700,640,480,4)
            camera.assert_called_once()

    def test_old_camera_profile_not_reused_for_new_device(self):
        cv = Mock(CAP_DSHOW=700, CAP_MSMF=1400)
        with patch.object(hm,"_open_capture",return_value=None) as opened:
            result = hm.open_camera(cv,{"camera_index":3,"camera":{"backend":"dshow","w":123,"h":456}},verify=False)
            self.assertIsNone(result)
            self.assertTrue(opened.call_count)
            self.assertTrue(all(call.args[-1] == 3 and call.args[2] != 123 for call in opened.call_args_list))

if __name__ == "__main__":
    unittest.main()
