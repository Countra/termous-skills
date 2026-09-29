"""原生进程接口使用替身，禁止测试探测真实 Termous 实例。"""

import ctypes
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/termous-desktop/scripts"
sys.path.insert(0, str(SCRIPTS))
import desktop_processes as processes


class ProcessTests(unittest.TestCase):
    def test_windows_filters_sessions_matches_paths_and_closes_handles(self):
        api = Mock()
        api.CreateToolhelp32Snapshot.return_value = 100
        candidates = iter([(11, "Termous.exe"), (22, "Termous.exe"), (33, "unrelated.exe")])

        def next_entry(handle, pointer):
            candidate = next(candidates, None)
            if candidate is None:
                return False
            pointer._obj.pid, pointer._obj.name = candidate
            return True

        def session(pid, pointer):
            pointer._obj.value = 2 if pid == 22 else 1
            return True

        def path(handle, flags, buffer, size):
            buffer.value = r"C:\Termous\Termous.exe"
            return True

        api.Process32FirstW.side_effect = next_entry
        api.Process32NextW.side_effect = next_entry
        api.ProcessIdToSessionId.side_effect = session
        api.OpenProcess.return_value = 200
        api.QueryFullProcessImageNameW.side_effect = path
        with patch.object(ctypes, "WinDLL", return_value=api, create=True), patch.object(ctypes, "get_last_error", return_value=18, create=True):
            rows, unknown = processes.windows_processes()
        self.assertEqual(rows, [{"pid": 11, "executable_path": r"C:\Termous\Termous.exe"}])
        self.assertFalse(unknown)
        api.OpenProcess.assert_called_once_with(0x1000, False, 11)
        self.assertEqual([call.args[0] for call in api.CloseHandle.call_args_list], [200, 100])

    def test_windows_denied_process_is_unknown(self):
        api = Mock()
        api.CreateToolhelp32Snapshot.return_value = 100
        api.Process32NextW.return_value = False
        api.OpenProcess.return_value = None

        def first(handle, pointer):
            pointer._obj.pid, pointer._obj.name = 22, "Termous.exe"
            return True

        def session(pid, pointer):
            pointer._obj.value = 1
            return True

        api.Process32FirstW.side_effect = first
        api.ProcessIdToSessionId.side_effect = session
        with patch.object(ctypes, "WinDLL", return_value=api, create=True), patch.object(ctypes, "get_last_error", return_value=18, create=True):
            self.assertEqual(processes.windows_processes(), ([], True))
        api.CloseHandle.assert_called_once_with(100)

    def test_mac_uses_current_uid_and_filters_application_name(self):
        api = Mock()

        def listing(kind, uid, buffer, size):
            self.assertEqual((kind, uid), (5, 42))
            if buffer is not None:
                buffer[0], buffer[1] = 11, 22
            return 8

        def name(pid, buffer, size):
            buffer.value = b"Termous" if pid == 11 else b"other"
            return len(buffer.value)

        def path(pid, buffer, size):
            buffer.value = b"/Applications/Termous.app/Contents/MacOS/Termous"
            return len(buffer.value)

        api.proc_listpids.side_effect = listing
        api.proc_name.side_effect = name
        api.proc_pidpath.side_effect = path
        with patch.object(ctypes, "CDLL", return_value=api), patch.object(os, "getuid", return_value=42, create=True):
            rows, unknown = processes.mac_processes()
        self.assertEqual([row["pid"] for row in rows], [11])
        self.assertFalse(unknown)
        api.proc_pidpath.assert_called_once()

    def test_linux_filters_core_and_reports_denied_or_deleted_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for pid, name in ((11, "Termous"), (22, "termous-core"), (33, "Termous.AppImage")):
                folder = root / str(pid)
                folder.mkdir()
                (folder / "comm").write_text(name)
            uid = root.stat().st_uid
            with patch.object(os, "getuid", return_value=uid, create=True), patch.object(os, "readlink", return_value="/app/Termous"):
                rows, unknown = processes.linux_processes(root)
                self.assertEqual(sorted(row["pid"] for row in rows), [11, 33])
                self.assertFalse(unknown)
            with patch.object(os, "getuid", return_value=uid, create=True), patch.object(os, "readlink", side_effect=PermissionError("denied")):
                self.assertEqual(processes.linux_processes(root), ([], True))
            with patch.object(os, "getuid", return_value=uid, create=True), patch.object(os, "readlink", return_value="/app/Termous (deleted)"):
                self.assertEqual(processes.linux_processes(root), ([], True))


if __name__ == "__main__":
    unittest.main()
