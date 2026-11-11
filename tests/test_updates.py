"""Release comparison, notification persistence, offline handling and bounded source parsing."""
import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import hand_mouse as hm

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.notify = Mock()
        self.stop = threading.Event()
        self.checker = hm.UpdateChecker(self.notify, self.stop)

    def test_newer_once_and_persisted_across_restart(self):
        with patch.object(hm.UpdateChecker, "latest", return_value="1.10.0"), patch.object(hm, "save_state") as save:
            self.checker.check()
            self.checker.check()
            self.assertEqual(self.notify.call_count, 1)
            save.assert_called_once_with(update_notified="1.10.0")
            hm.UpdateChecker(self.notify, self.stop, {"update_notified":"1.10.0"}).check()
            self.assertEqual(self.notify.call_count, 1)
            self.checker.check(manual=True)
            self.assertEqual(self.notify.call_count, 2)

    def test_same_or_older_never_prompts_downgrade(self):
        for version in (hm.APP_VERSION, "0.9.9"):
            with patch.object(hm.UpdateChecker, "latest", return_value=version):
                self.checker.check()
                self.notify.assert_not_called()
                self.checker.check(manual=True)
                self.assertIn("up to date", self.notify.call_args[0][0])
                self.notify.reset_mock()

    def test_offline_is_quiet_unless_manual(self):
        with patch.object(hm.UpdateChecker, "latest", side_effect=OSError("offline")):
            self.checker.check()
            self.notify.assert_not_called()
            self.checker.check(manual=True)
            self.assertIn("Could not check", self.notify.call_args[0][0])

    def test_shutdown_suppresses_notifications(self):
        self.stop.set()
        with patch.object(hm.UpdateChecker, "latest", return_value="2.0.0"):
            self.checker.check(manual=True)
        self.notify.assert_not_called()

    def test_parses_bounded_source_and_rejects_missing_or_invalid_version(self):
        for source, want in ((b'APP_VERSION = "1.2.10"\n', "1.2.10"),
                             (b'APP_VERSION = "oops"\n', None), (b'<html>error</html>', None)):
            response = Mock()
            response.read.return_value = source
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            with patch.object(hm.urllib.request, "urlopen", return_value=response) as request:
                if want:
                    self.assertEqual(hm.UpdateChecker.latest(), want)
                else:
                    with self.assertRaises(ValueError):
                        hm.UpdateChecker.latest()
                response.read.assert_called_once_with(16384)
                self.assertEqual(request.call_args.kwargs["timeout"], 8)

if __name__ == "__main__":
    unittest.main()
