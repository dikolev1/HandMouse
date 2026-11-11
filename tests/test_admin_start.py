"""Elevation requests preserve launch arguments and stop before app resources are opened."""
import ctypes
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import hand_mouse as hm

class AdminStart(unittest.TestCase):
    def test_already_admin_does_not_relaunch(self):
        shell = Mock()
        shell.IsUserAnAdmin.return_value = 1
        with patch.object(ctypes.windll,"shell32",shell):
            self.assertTrue(hm.ensure_administrator())
        shell.ShellExecuteW.assert_not_called()

    def test_relaunch_quotes_paths_and_preserves_flags(self):
        shell = Mock()
        shell.IsUserAnAdmin.return_value = 0
        shell.ShellExecuteW.return_value = 42
        script = r"C:\Users\A Person\Hand Mouse\hand_mouse.py"
        exe = r"C:\Program Files\Python\pythonw.exe"
        args = [script,"--preview","--debug","--restarted"]
        with patch.object(ctypes.windll,"shell32",shell), patch.object(hm,"SCRIPT",script), patch.object(sys,"executable",exe), patch.object(sys,"argv",args):
            self.assertFalse(hm.ensure_administrator())
        shell.ShellExecuteW.assert_called_once_with(None,"runas",exe,subprocess.list2cmdline(args),hm.HERE,0)

    def test_cancel_or_failed_request_exits_without_retry(self):
        for result in (None,5,31):
            shell = Mock()
            shell.IsUserAnAdmin.return_value = 0
            shell.ShellExecuteW.return_value = result
            with patch.object(ctypes.windll,"shell32",shell), patch.object(hm,"message_box") as notice:
                self.assertFalse(hm.ensure_administrator())
                notice.assert_called_once()
            self.assertEqual(shell.ShellExecuteW.call_count,1)

    def test_parent_exits_before_logs_mutex_or_camera(self):
        with patch.object(sys,"argv",[hm.SCRIPT]), patch.object(hm,"ensure_administrator",return_value=False), patch.object(hm,"single_instance") as mutex, patch.object(hm,"run") as run, patch("logging.handlers.RotatingFileHandler") as logs:
            self.assertEqual(hm.main(),0)
            mutex.assert_not_called()
            run.assert_not_called()
            logs.assert_not_called()

if __name__ == "__main__":
    unittest.main()
