"""Read installation metadata without executing the discovered application."""

import configparser
import ntpath
import os
from pathlib import Path
import plistlib
import re
import shlex
import stat
import sys
from xml.parsers.expat import ExpatError

APP_ID = "dev.termous.app"


def regular_file(path):
    try:
        return stat.S_ISREG(Path(path).stat().st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False


def installation(executable, version, source, kind, launch_path=None):
    return {"app_id": APP_ID, "version": version, "source": source, "kind": kind,
            "executable_path": str(executable), "install_location": str(Path(executable).parent),
            "launch_path": str(launch_path or executable)}


def windows_installation(registry=None):
    if registry is None:
        import winreg as registry
    for hive, label in ((registry.HKEY_CURRENT_USER, "HKCU"), (registry.HKEY_LOCAL_MACHINE, "HKLM")):
        try:
            key = registry.OpenKey(hive, r"Software\Termous\Install", 0,
                                   registry.KEY_READ | registry.KEY_WOW64_64KEY)
        except FileNotFoundError:
            continue
        with key as handle:
            try:
                values = {name: registry.QueryValueEx(handle, name) for name in
                          ("SchemaVersion", "AppId", "DisplayVersion", "InstallLocation", "ExecutablePath")}
            except FileNotFoundError:
                continue
        if values["SchemaVersion"] != (1, registry.REG_DWORD):
            continue
        if any(kind != registry.REG_SZ or not isinstance(value, str)
               for name, (value, kind) in values.items() if name != "SchemaVersion"):
            continue
        data = {name: value for name, (value, _) in values.items()}
        if data["AppId"] != APP_ID or not data["DisplayVersion"].strip():
            continue
        directory, executable = data["InstallLocation"], data["ExecutablePath"]
        # Reject arguments, control characters and drive-relative paths before probing files.
        if any(re.search(r'[\x00-\x1f"<>|?*]', value) for value in (directory, executable)):
            continue
        if not all(ntpath.isabs(value) and ntpath.splitdrive(value)[0]
                   for value in (directory, executable)):
            continue
        directory, executable = ntpath.normpath(directory), ntpath.normpath(executable)
        if ntpath.normcase(executable) != ntpath.normcase(ntpath.join(directory, "Termous.exe")):
            continue
        if regular_file(executable):
            result = installation(executable, data["DisplayVersion"], label, "windows")
            result["install_location"] = directory
            return result
    return None


def mac_installation(bundle, source):
    bundle = Path(bundle)
    info_path = bundle / "Contents" / "Info.plist"
    if not regular_file(info_path):
        return None
    try:
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
    except (plistlib.InvalidFileException, ValueError, ExpatError):
        return None
    if not isinstance(info, dict) or info.get("CFBundleIdentifier") != APP_ID:
        return None
    name = info.get("CFBundleExecutable")
    if not isinstance(name, str) or name != "Termous":
        return None
    executable = bundle / "Contents" / "MacOS" / name
    if not regular_file(executable) or not os.access(executable, os.X_OK):
        return None
    version = info.get("CFBundleShortVersionString")
    if not isinstance(version, str) or not version.strip():
        version = None
    result = installation(executable.resolve(), version, source, "macos", bundle.resolve())
    result["install_location"] = str(bundle.resolve())
    return result


def linux_installation(executable, source):
    executable = Path(executable)
    if not executable.is_absolute() or not regular_file(executable):
        return None
    executable = executable.resolve()
    with executable.open("rb") as stream:
        header = stream.read(12)
    if not header.startswith(b"\x7fELF") or not os.access(executable, os.X_OK):
        return None
    appimage = header[8:11] in (b"AI\x01", b"AI\x02")
    if appimage:
        if not executable.name.lower().startswith("termous"):
            return None
    elif executable.name not in ("Termous", "termous"):
        return None
    # AppImage has no standard static version field. Never execute --version to guess it.
    return installation(executable, None, source, "appimage" if appimage else "linux")


def linux_desktop_entries():
    data_home = os.environ.get("XDG_DATA_HOME", "")
    roots = [Path(data_home) if Path(data_home).is_absolute() else Path.home() / ".local/share"]
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots.extend(Path(value) for value in data_dirs.split(":")
                 if Path(value).is_absolute())
    for root in dict.fromkeys(roots):
        for name in ("termous.desktop", "Termous.desktop", "dev.termous.app.desktop"):
            yield root / "applications" / name


def desktop_executable(path):
    if not regular_file(path):
        return None
    config = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        with path.open(encoding="utf-8") as stream:
            config.read_file(stream)
        entry = config["Desktop Entry"]
        if entry.get("Type") != "Application" or entry.get("Hidden", "false").lower() == "true":
            return None
        # Only a direct executable plus optional standard file/URL placeholders is accepted.
        # Wrappers, shell commands, environment assignments and extra arguments are not executed.
        args = shlex.split(entry.get("Exec", ""), posix=True)
        if not args or any(arg not in ("%f", "%F", "%u", "%U") for arg in args[1:]):
            return None
        if not Path(args[0]).is_absolute() or "%" in args[0]:
            return None
        return args[0]
    except (configparser.Error, KeyError, ValueError, UnicodeError):
        return None


def discover(explicit_path=None):
    if sys.platform == "win32":
        if explicit_path:
            raise ValueError("Windows discovery uses the installer registry record; --path is not supported.")
        return windows_installation()
    if explicit_path and not Path(explicit_path).is_absolute():
        raise ValueError("--path must be an absolute path supplied by the user.")
    if sys.platform == "darwin":
        candidates = [Path(explicit_path)] if explicit_path else [Path.home() / "Applications/Termous.app", Path("/Applications/Termous.app")]
        for bundle in candidates:
            result = mac_installation(bundle, "explicit" if explicit_path else "applications")
            if result:
                return result
    elif sys.platform.startswith("linux"):
        if explicit_path:
            return linux_installation(explicit_path, "explicit")
        for entry in linux_desktop_entries():
            executable = desktop_executable(entry)
            if executable:
                result = linux_installation(executable, "desktop_entry")
                if result:
                    return result
    else:
        raise ValueError("Supported platforms are Windows, macOS and Linux.")
    return None
