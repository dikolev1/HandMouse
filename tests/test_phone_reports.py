"""Regressions for the phone reports, including measured November 5 distances.

Only fake hands and Windows calls: never opens a camera or sends real keys.
"""
import contextlib
import io
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T

hm = T.hm


class PhoneReports(unittest.TestCase):
    def setUp(self):
        self.mouse = T.V.FakeMouse()
        self.engine = hm.SecondHandKeys(self.mouse)
        self.now = 0.0
        original_distances = hm.tip_distances_2d
        original_thumb = hm.thumb_out
        self.addCleanup(patch.stopall)
        patch.object(hm, "tip_distances_2d", side_effect=lambda h: h.__dict__.get(
            "readings2", original_distances(h))).start()
        patch.object(hm, "thumb_index_2d", side_effect=lambda h: hm.tip_distances_2d(h)["index"]).start()
        patch.object(hm, "thumb_out", side_effect=lambda h: h.__dict__.get(
            "out", original_thumb(h))).start()

    def feed(self, factory, frames=8):
        for _ in range(frames):
            self.engine.update(factory(), self.now)
            self.now += 1 / 16

    def events(self):
        return T.keys(self.mouse)

    def sample(self, d3, d2, pose="middle"):
        h = T.left(pose)
        h.__dict__["side"] = {"x1": d3[0], "x2": float("inf")}
        h.__dict__["pinch"] = d3[1:]
        h.__dict__["readings2"] = dict(zip(hm.TIPS, d2))
        return h

    def test_copy_and_paste_ignore_falsely_close_index_depth(self):
        for pose, d3, d2, key in (
            ("middle", (.10, .40, .55), (.45, .14, .60), "C"),
            ("ring", (.12, .55, .40), (.50, .60, .14), "V"),
        ):
            with self.subTest(pose=pose):
                self.mouse.events.clear()
                self.feed(lambda: self.sample(d3, d2, pose))
                self.feed(T.left, 16)
                self.assertEqual(self.events(), [("keys", (T.CTRL, ord(key)))])

    def test_open_hand_depth_fallback_does_not_trigger_alt_tab(self):
        # Live false Alt+Tab, 2026-11-06 14:40:04-06 and 14:40:27.
        for d3, d2 in (((.37, .66, .95), (.41, .70, 1.17)),
                       ((.39, .86, 1.12), (.54, .96, 1.27)),
                       ((.40, .96, 1.16), (.54, 1.06, 1.33)),
                       ((.38, .73, .82), (.51, .83, .94)),
                       ((.42, .73, .80), (.54, .83, .95))):
            with self.subTest(d3=d3):
                self.mouse.events.clear()
                self.feed(lambda: self.sample(d3, d2), 32)
                self.feed(T.left, 16)
                self.assertEqual(self.events(), [])

    def test_screenshot_unequal_contacts_from_log(self):
        for mid, ring in ((.14, .23), (.08, .14), (.11, .18),
                          (.14, .33), (.17, .36), (.17, .28), (.23, .32), (.04, .14), (.21, .38)):
            with self.subTest(mid=mid, ring=ring):
                self.mouse.events.clear()
                self.feed(lambda: self.sample((.60, mid, ring), (.60, mid, ring), "middle+ring"))
                self.feed(T.left, 16)
                self.assertEqual(self.events(), [("keys", (T.K["printscreen"],))])

    def test_screenshot_ignores_false_index_depth(self):
        self.feed(lambda: self.sample((.12, .18, .20), (.55, .10, .16), "middle+ring"))
        self.feed(T.left, 16)
        self.assertEqual(self.events(), [("keys", (T.K["printscreen"],))])

    def test_keyboard_double_pinch_unequal_contacts(self):
        # November 5: index .11 / middle .19 was read as Alt+Tab, next tap as voice input.
        pinch = lambda: self.sample((.11, .19, .59), (.15, .19, .69), "index+middle")
        self.feed(pinch, 4)
        self.feed(T.left, 3)
        self.feed(pinch, 4)
        self.feed(T.left, 16)
        self.assertEqual(self.events(), [("osk",)])

    def test_keyboard_live_pair_drift_and_natural_double_tap_gap(self):
        # Labelled keyboard test 14:47:41: second tap's middle read .28, first read .26.
        self.feed(lambda: self.sample((.19, .26, .65), (.19, .26, .65), "index+middle"), 4)
        self.feed(T.left, 10)  # .625 s opening/reforming at a slow camera frame rate
        self.feed(lambda: self.sample((.18, .28, .67), (.18, .28, .67), "index+middle"), 3)
        self.feed(T.left, 20)
        self.assertEqual(self.events(), [("osk",)])

    def test_keyboard_live_first_pair_is_not_alt_tab(self):
        for idx, mid in ((.19, .29), (.06, .32), (.12, .31)):
            with self.subTest(index=idx, middle=mid):
                self.mouse.events.clear()
                pinch = lambda: self.sample((idx, mid, .65), (idx, mid, .69), "index+middle")
                self.feed(pinch, 4)
                self.feed(T.left, 5)
                self.feed(pinch, 4)
                self.feed(T.left, 20)
                self.assertEqual(self.events(), [("osk",)])

    def test_pending_keyboard_pair_does_not_take_a_clear_copy_pinch(self):
        self.feed(lambda: self.sample((.19, .26, .65), (.19, .26, .65), "index+middle"), 4)
        self.feed(T.left, 3)
        self.feed(lambda: self.sample((.27, .15, .50), (.27, .15, .50)), 4)
        self.feed(T.left, 20)
        self.assertEqual(self.events(), [("keys", (T.WIN, ord("H"))), ("keys", (T.CTRL, ord("C")))])

    def test_tucking_thumb_cancels_media_without_play_or_esc(self):
        self.feed(T.thumbs, 8)
        def tucked():
            h = T.left("fist")
            h.__dict__["out"] = .24  # a fist (< .30), but still above the old keep threshold (.18)
            return h
        self.feed(tucked, 8)
        self.assertEqual(self.events(), [])

    def test_open_hand_ends_media_session(self):
        self.feed(lambda: T.thumbs(.3), 8)
        self.feed(T.left, 2)
        # New pose at another location, less than .3 s later, has not moved sideways itself.
        self.feed(lambda: T.thumbs(.55), 8)
        self.feed(T.left, 8)
        self.assertEqual(self.events(), [("keys", (T.K["playpause"],))])

    def test_user_music_pose_then_open_plays_once(self):
        self.feed(T.thumbs, 10)
        self.feed(T.left, 16)
        self.assertEqual(self.events(), [("keys", (T.K["playpause"],))])

    def test_quick_music_pose_then_open(self):
        self.feed(T.thumbs, 3)  # .125 s of clear pose at 16 fps
        self.feed(T.left, 8)
        self.assertEqual(self.events(), [("keys", (T.K["playpause"],))])

    def test_switcher_navigation_uses_tab_chords_not_arrow_keys(self):
        self.engine._open_switcher(T.left("index", .3))
        self.mouse.events.clear()
        self.engine._switch_step(T.left("index", .42), 1)
        self.assertEqual(self.events(), [("keys", (T.K["tab"],))] * 2)
        self.mouse.events.clear()
        self.engine._switch_step(T.left("index", .3), 1)
        self.assertTrue(self.events())
        self.assertTrue(all(e == ("keys", (T.K["shift"], T.K["tab"])) for e in self.events()))

    def test_held_index_survives_moderate_picture_and_depth_drift(self):
        self.feed(lambda: T.left("index"), 12)
        for k in range(12):
            def drift(k=k):
                h = self.sample((.65, .90, 1.10), (.38, 1.0, 1.2), "index")
                h.img = [(x + .01 * k, y) for x, y in h.img]
                return h
            self.feed(drift, 1)
        self.assertTrue(self.engine.switcher)
        self.assertNotIn(("key", T.ALT, False), self.events())

    def test_native_window_step_repairs_lost_alt_state(self):
        mouse = hm.WinMouse.__new__(hm.WinMouse)
        mouse.u = Mock()
        mouse.u.GetAsyncKeyState.return_value = 1  # low bit is NOT the key-down bit
        mouse.key, mouse.keys = Mock(), Mock()
        mouse.switch_window_step(1)
        mouse.key.assert_called_once_with(T.ALT, True)
        mouse.keys.assert_called_once_with([T.K["tab"]])
        mouse.key.reset_mock()
        mouse.keys.reset_mock()
        mouse.u.GetAsyncKeyState.return_value = 0x8000
        mouse.switch_window_step(-1)
        mouse.key.assert_not_called()
        mouse.keys.assert_called_once_with([T.K["shift"], T.K["tab"]])

    def test_user_sideways_thumb_pose_then_open(self):
        def sideways():
            h = T.thumbs()
            base = h.world[2]
            return T.with_thumb(h, (base[0] + .12, base[1], base[2]))
        self.assertGreater(hm.thumb_angle(sideways()), 70)
        self.feed(sideways, 10)
        self.feed(T.left, 16)
        self.assertEqual(self.events(), [("keys", (T.K["playpause"],))])

    def test_pinch_dropout_cannot_turn_into_music_swipe(self):
        self.feed(lambda: T.left("index"), 12)
        # While moving, all fingers and the contact can be misread for longer than release debounce.
        self.feed(lambda: T.thumbs(.3), 12)
        for k in range(16):
            self.feed(lambda k=k: T.thumbs(.3 + .012 * k), 1)
        self.feed(T.left, 12)
        media = {T.K[n] for n in ("nexttrack", "prevtrack", "playpause")}
        self.assertFalse(any(e[0] == "keys" and any(v in media for v in e[1]) for e in self.events()))
        self.mouse.events.clear()
        self.feed(T.left, 8)
        self.feed(T.thumbs, 10)
        self.feed(T.left, 16)
        self.assertEqual(self.events(), [("keys", (T.K["playpause"],))])

    def test_folded_index_contact_never_becomes_track_swipe(self):
        def contact(x):
            h = self.sample((.18, .8, .9), (.15, .9, 1.0), "index")
            h.__dict__["ext"] = [1.2] * 4  # model mistakes the OK sign for folded fingers
            h.__dict__["out"] = .65
            # Translation, not a change to the fingertip contact.
            h.img = [(px + x, py) for px, py in h.img]
            return h
        self.feed(lambda: contact(0), 10)
        for k in range(12):
            self.feed(lambda k=k: contact(k * .015), 1)
        self.feed(T.left, 10)
        media = {T.K[n] for n in ("nexttrack", "prevtrack", "playpause")}
        self.assertFalse(any(e[0] == "keys" and any(v in media for v in e[1]) for e in self.events()))
        self.assertIn(("key", T.ALT, True), self.events())
        self.assertIn(("key", T.ALT, False), self.events())

    def test_visible_keyboard_window_is_closed(self):
        mouse = hm.WinMouse.__new__(hm.WinMouse)
        mouse.u = Mock()
        mouse.u.FindWindowW.return_value = 123
        mouse.u.IsWindowVisible.return_value = True
        with patch.object(hm.os, "startfile") as launch:
            mouse.toggle_keyboard()
        mouse.u.PostMessageW.assert_called_once()
        launch.assert_not_called()

    def test_hidden_keyboard_window_is_reopened(self):
        mouse = hm.WinMouse.__new__(hm.WinMouse)
        mouse.u = Mock()
        mouse.u.FindWindowW.return_value = 123
        mouse.u.IsWindowVisible.return_value = False
        with patch.object(hm.os, "startfile") as launch:
            mouse.toggle_keyboard()
        launch.assert_called_once()
        mouse.u.PostMessageW.assert_not_called()

    def test_keyboard_launch_failure_is_not_shown_as_success(self):
        self.mouse.toggle_keyboard = Mock(side_effect=OSError("launch failed"))
        self.engine._do("index+middle twice")
        self.assertIn("failed", self.engine.display(self.now).lower())


if __name__ == "__main__":
    unittest.main()
