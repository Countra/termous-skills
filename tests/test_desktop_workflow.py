"""使用隔离安装记录和系统接口验证跨平台桌面工作流。"""

import contextlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/termous-desktop/scripts"
sys.path.insert(0, str(SCRIPTS))
import desktop_discovery as discovery
import termous_desktop as desktop


class RegistryFixture:
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE = 1, 2
    KEY_READ, KEY_WOW64_64KEY, REG_SZ, REG_DWORD = 1, 256, 1, 4

    def __init__(self):
        self.records = {hive: {"SchemaVersion": (1, 4), "AppId": (discovery.APP_ID, 1),
                              "DisplayVersion": ("1.2.3", 1), "InstallLocation": (f"C:\\Scope{hive}", 1),
                              "ExecutablePath": (f"C:\\Scope{hive}\\Termous.exe", 1)} for hive in (1, 2)}
        self.closed = []

    def OpenKey(self, hive, key, reserved, access):
        assert key == r"Software\Termous\Install" and access == 257
        if hive not in self.records:
            raise FileNotFoundError()
        @contextlib.contextmanager
        def opened():
            try:
                yield hive
            finally:
                self.closed.append(hive)
        return opened()

    def QueryValueEx(self, key, name):
        try:
            return self.records[key][name]
        except KeyError:
            raise FileNotFoundError() from None


class DiscoveryTests(unittest.TestCase):
    def test_empty_xdg_data_dirs_uses_system_defaults(self):
        with patch.object(discovery, "Path", PurePosixPath), patch.dict(os.environ, {
            "XDG_DATA_HOME": "/home/fixture/.local/share", "XDG_DATA_DIRS": "",
        }):
            entries = list(discovery.linux_desktop_entries())
        self.assertEqual(entries[0], PurePosixPath("/home/fixture/.local/share/applications/termous.desktop"))
        self.assertIn(PurePosixPath("/usr/local/share/applications/termous.desktop"), entries)
        self.assertIn(PurePosixPath("/usr/share/applications/termous.desktop"), entries)

    def test_windows_priority_types_and_fallback(self):
        registry = RegistryFixture()
        with patch.object(discovery, "regular_file", return_value=True):
            self.assertEqual(discovery.windows_installation(registry)["source"], "HKCU")
            for field, invalid in (("SchemaVersion", (0, 4)), ("SchemaVersion", ("1", 1)),
                                   ("AppId", ([discovery.APP_ID], 7)), ("AppId", ("other", 1)),
                                   ("ExecutablePath", ("C:relative", 1)),
                                   ("InstallLocation", ("C:\\Invalid\0Path", 1)),
                                   ("ExecutablePath", ("C:\\Other\\Termous.exe", 1))):
                with self.subTest(field=field, invalid=invalid):
                    fixture = RegistryFixture()
                    fixture.records[1][field] = invalid
                    self.assertEqual(discovery.windows_installation(fixture)["source"], "HKLM")
                    self.assertEqual(fixture.closed, [1, 2])

    def test_windows_missing_executable_and_permission_error(self):
        registry = RegistryFixture()
        with patch.object(discovery, "regular_file", side_effect=[False, True]):
            self.assertEqual(discovery.windows_installation(registry)["source"], "HKLM")
        with patch.object(discovery, "regular_file", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                discovery.windows_installation(registry)
        registry.records.clear()
        self.assertIsNone(discovery.windows_installation(registry))

    def test_mac_bundle_metadata_and_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "Termous.app"
            executable = bundle / "Contents/MacOS/Termous"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture only")
            info = bundle / "Contents/Info.plist"
            data = {"CFBundleIdentifier": discovery.APP_ID, "CFBundleExecutable": "Termous",
                    "CFBundleShortVersionString": "1.2.3"}
            info.write_bytes(plistlib.dumps(data))
            with patch.object(discovery.os, "access", return_value=True):
                result = discovery.mac_installation(bundle, "explicit")
                self.assertEqual(result["version"], "1.2.3")
                self.assertEqual(result["launch_path"], str(bundle.resolve()))
                self.assertEqual(result["install_location"], str(bundle.resolve()))
                for key, value in (("CFBundleIdentifier", "other"), ("CFBundleExecutable", "../Other")):
                    info.write_bytes(plistlib.dumps({**data, key: value}))
                    self.assertIsNone(discovery.mac_installation(bundle, "explicit"))
                info.write_bytes(b"<?xml version='1.0'?><plist><dict>")
                self.assertIsNone(discovery.mac_installation(bundle, "explicit"))

    def test_linux_appimage_does_not_execute_to_get_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "Termous-1.2.3.AppImage"
            executable.write_bytes(b"\x7fELF\x02\x01\x01\x00AI\x02\x00")
            with patch.object(discovery.os, "access", return_value=True):
                result = discovery.linux_installation(executable, "explicit")
                self.assertEqual(result["kind"], "appimage")
                self.assertIsNone(result["version"])
            with patch.object(discovery.os, "access", return_value=False):
                self.assertIsNone(discovery.linux_installation(executable, "explicit"))
            executable.write_text("not an executable")
            self.assertIsNone(discovery.linux_installation(executable, "explicit"))

    def test_linux_desktop_entry_accepts_only_direct_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = Path(temporary) / "termous.desktop"
            executable = str(Path(temporary) / "Termous AppImage")
            # 使用当前平台的绝对路径，以便 Windows CI 同样验证解析行为。
            command = '"' + executable.replace("\\", "\\\\") + '" %U'
            entry.write_text(f"[Desktop Entry]\nType=Application\nExec={command}\n", encoding="utf-8")
            self.assertEqual(discovery.desktop_executable(entry), executable)
            for command in ('sh -c "Termous"', '/bin/Termous --no-sandbox', 'env X=1 /bin/Termous'):
                entry.write_text(f"[Desktop Entry]\nType=Application\nExec={command}\n", encoding="utf-8")
                self.assertIsNone(discovery.desktop_executable(entry))

    def test_platform_routing_and_explicit_path(self):
        with patch.object(discovery.sys, "platform", "darwin"), patch.object(discovery, "mac_installation", side_effect=[None, {"ok": True}]) as lookup:
            self.assertEqual(discovery.discover(), {"ok": True})
            self.assertEqual(lookup.call_count, 2)
        with patch.object(discovery.sys, "platform", "win32"):
            with self.assertRaises(ValueError):
                discovery.discover("C:\\Termous.exe")
        with patch.object(discovery.sys, "platform", "linux"):
            with self.assertRaises(ValueError):
                discovery.discover("relative.AppImage")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.install = {"executable_path": os.path.abspath("Termous"), "version": "1.0",
                        "install_location": os.path.abspath("."), "launch_path": os.path.abspath("Termous.app")}
        self.discover = patch.object(desktop, "discover", return_value=self.install).start()
        self.processes = patch.object(desktop, "processes", return_value=([], False)).start()
        self.launch = patch.object(desktop, "launch").start()
        self.addCleanup(patch.stopall)

    def test_info_and_status_do_not_launch(self):
        self.assertEqual(desktop.execute("info")["installation"], self.install)
        self.processes.assert_not_called()
        self.assertEqual(desktop.execute("status")["process_state"], "not_detected")
        self.launch.assert_not_called()

    def test_existing_unknown_other_and_missing_installation_suppress_launch(self):
        for rows, unknown, expected in (([{"pid": 1, "executable_path": self.install["executable_path"]}], False, "detected"),
                                        ([], True, "unknown"),
                                        ([{"pid": 2, "executable_path": os.path.abspath("other/Termous")}], False, "other_path")):
            self.processes.return_value = (rows, unknown)
            result = desktop.execute("start")
            self.assertEqual(result["process_state"], expected)
            self.assertFalse(result["launch_requested"])
        self.discover.return_value = None
        self.processes.return_value = ([], False)
        self.assertFalse(desktop.execute("start")["launch_requested"])
        self.launch.assert_not_called()

    def test_launch_once_and_report_observed_process(self):
        self.processes.side_effect = [([], False), ([{"pid": 123, "executable_path": self.install["executable_path"]}], False)]
        result = desktop.execute("start", wait_seconds=0)
        self.assertTrue(result["launch_requested"])
        self.assertEqual(result["process_ids"], [123])
        self.launch.assert_called_once_with(self.install)

    def test_timeout_and_failures_never_relaunch(self):
        result = desktop.execute("start", wait_seconds=0)
        self.assertEqual(result["process_state"], "not_detected")
        self.launch.assert_called_once()
        self.launch.reset_mock()
        self.launch.side_effect = OSError("fixture failed")
        self.assertEqual(desktop.execute("start")["error"]["code"], "launch_unconfirmed")
        self.launch.assert_called_once()

    def test_installation_change_and_post_launch_query_failure(self):
        self.discover.side_effect = [self.install, None]
        with self.assertRaises(ValueError):
            desktop.execute("start")
        self.launch.assert_not_called()
        self.discover.side_effect = None
        self.processes.side_effect = [([], False), OSError("denied")]
        result = desktop.execute("start")
        self.assertEqual(result["error"]["code"], "state_unavailable")
        self.launch.assert_called_once()

    def test_cli_json_error_and_success(self):
        for failure in (None, PermissionError("fixture denied")):
            self.discover.side_effect = failure
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = desktop.main(["info"])
            result = json.loads(output.getvalue())
            self.assertEqual(result["schema_version"], 1)
            self.assertEqual(code, 1 if failure else 0)
            self.assertEqual(result["ok"], failure is None)


class LaunchTests(unittest.TestCase):
    def test_headless_start_reports_no_launch_request(self):
        install = {"executable_path": "/app/Termous", "install_location": "/app"}
        with patch.object(desktop.sys, "platform", "linux"), patch.dict(os.environ, {}, clear=True), \
                patch.object(desktop, "discover", return_value=install), \
                patch.object(desktop, "processes", return_value=([], False)), \
                patch.object(subprocess, "Popen") as popen:
            result = desktop.execute("start")
        self.assertFalse(result["launch_requested"])
        self.assertEqual(result["process_state"], "not_detected")
        self.assertEqual(result["error"]["code"], "launch_unavailable")
        popen.assert_not_called()

    def test_launch_uses_argument_array_without_shell(self):
        install = {"executable_path": "/Applications/Termous.app/Contents/MacOS/Termous",
                   "install_location": "/Applications/Termous.app/Contents/MacOS", "launch_path": "/Applications/Termous.app"}
        with patch.object(desktop.sys, "platform", "darwin"), patch.object(subprocess, "run") as run:
            desktop.launch(install)
            self.assertEqual(run.call_args.args[0], ["/usr/bin/open", "-a", install["launch_path"]])
            self.assertNotIn("shell", run.call_args.kwargs)
        with patch.object(desktop.sys, "platform", "linux"), patch.dict(os.environ, {"DISPLAY": ":fixture", "ELECTRON_RUN_AS_NODE": "1"}), patch.object(subprocess, "Popen") as popen:
            desktop.launch(install)
            self.assertEqual(popen.call_args.args[0], [install["executable_path"]])
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertNotIn("ELECTRON_RUN_AS_NODE", popen.call_args.kwargs["env"])
        with patch.object(desktop.sys, "platform", "linux"), patch.dict(os.environ, {}, clear=True), patch.object(subprocess, "Popen") as popen:
            with self.assertRaises(ValueError):
                desktop.launch(install)
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
