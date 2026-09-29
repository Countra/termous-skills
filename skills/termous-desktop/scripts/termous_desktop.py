#!/usr/bin/env python3
"""Discover, inspect or launch Termous using only the Python standard library."""

import argparse
import json
import os
import subprocess
import sys
import time

# Running the installed helper must not leave bytecode files in the Skill bundle.
sys.dont_write_bytecode = True
from desktop_discovery import discover
from desktop_processes import processes


def state(installation):
    rows, unknown = processes()
    expected = os.path.normcase(os.path.realpath(installation["executable_path"])) if installation else None
    matched = [row["pid"] for row in rows
               if expected and os.path.normcase(os.path.realpath(row["executable_path"])) == expected]
    other = [row["pid"] for row in rows if row["pid"] not in matched]
    status = "detected" if matched else "unknown" if unknown else "other_path" if other else "not_detected"
    return {"installation": installation, "process_state": status,
            "process_ids": sorted(matched), "other_process_ids": sorted(other)}


def launch(installation):
    executable = installation["executable_path"]
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "env": env, "close_fds": True}
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", "-a", installation["launch_path"]],
                       check=True, timeout=10, **options)
        return
    if sys.platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        raise ValueError("No graphical desktop session is available; launch from the local desktop.")
    if sys.platform == "win32":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    subprocess.Popen([executable], cwd=installation["install_location"], **options)


def execute(action, explicit_path=None, wait_seconds=10):
    installation = discover(explicit_path)
    if action == "info":
        return {"installation": installation}
    before = state(installation)
    if action == "status":
        return before
    if installation is None or before["process_state"] != "not_detected":
        return {**before, "launch_requested": False}
    # Recheck metadata immediately before launching; never silently switch installations.
    if discover(explicit_path) != installation:
        raise ValueError("Installation changed before launch; inspect it again.")
    try:
        launch(installation)
    except ValueError as error:
        return {**before, "launch_requested": False,
                "error": {"code": "launch_unavailable", "message": str(error)}}
    except (OSError, subprocess.SubprocessError) as error:
        return {**before, "launch_requested": True, "process_state": "unknown",
                "error": {"code": "launch_unconfirmed", "message": str(error)}}
    after = before
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            after = state(installation)
        except (OSError, ValueError) as error:
            return {**before, "launch_requested": True, "process_state": "unknown",
                    "error": {"code": "state_unavailable", "message": str(error)}}
        if after["process_state"] != "not_detected" or time.monotonic() >= deadline:
            break
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    return {**after, "launch_requested": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("info", "status", "start"))
    parser.add_argument("--path", help="User-supplied absolute .app, AppImage or Linux executable path")
    parser.add_argument("--wait-seconds", type=int, choices=range(0, 31), default=10,
                        metavar="0..30", help="Bounded post-launch polling duration (default: 10)")
    args = parser.parse_args(argv)
    result = {"schema_version": 1, "platform": sys.platform, "action": args.action}
    try:
        result.update(execute(args.action, args.path, args.wait_seconds))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result["error"] = {"code": "operation_failed", "message": str(error)}
    result["ok"] = "error" not in result
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
