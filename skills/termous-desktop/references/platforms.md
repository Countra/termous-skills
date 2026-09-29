# Platform Discovery and Results

All operations use Python's standard library. The helper never invokes the discovered executable to obtain its version and never reads process command lines or environment blocks.

## Windows

Read `Software\Termous\Install` in the 64-bit registry view, preferring HKCU over HKLM. Accept `SchemaVersion=1`, `AppId=dev.termous.app`, typed string metadata, and an existing `Termous.exe` in the recorded installation directory. Missing or invalid records fall back to the other scope; permission failures are reported.

Older installers, manually moved executables, and upgrades in progress may have no valid record. Missing metadata does not prove the software is not installed. Process detection uses native Windows APIs and matches executable paths within the current Windows session. No PowerShell or WMI dependency is required.

## macOS

Check `~/Applications/Termous.app`, then `/Applications/Termous.app`, or the explicit `.app` path supplied with `--path`. Validate `Contents/Info.plist`, the bundle identifier `dev.termous.app`, and the `Termous` executable. Read the version from `CFBundleShortVersionString`; do not invent one if absent.

Native `libproc` calls inspect processes owned by the current user and compare executable paths. Launch uses the system `/usr/bin/open -a` command with the validated bundle path and no shell. Applications installed elsewhere require an explicit path.

## Linux

Termous currently distributes an AppImage. There is no universal installation directory or registry. Check the standard XDG application directories for `termous.desktop`, `Termous.desktop`, or `dev.termous.app.desktop`. Only a direct absolute `Exec` path with optional file/URL placeholders is supported; wrappers, shell commands, environment assignments, and custom arguments are not executed.

If no usable entry exists, request the AppImage's absolute path and pass it with `--path`. An extracted `Termous` or `termous` executable is also supported. Validate the file type and execute permission without changing permissions. The helper reports `version: null` because AppImage has no standard static application-version field; a filename is not reliable version metadata.

Inspect `/proc` for processes owned by the current user. Match the executable path where possible. AppImage can execute from a temporary mount; if that path cannot be linked to the selected AppImage, report `other_path` and suppress another launch rather than guessing. Headless sessions cannot launch the GUI; the local desktop must provide `DISPLAY` or `WAYLAND_DISPLAY`.

## JSON result

Results include `schema_version`, `platform`, `action`, `ok`, and `installation`. Installation metadata contains `app_id`, `version`, `source`, `kind`, `executable_path`, `install_location`, and `launch_path`. A null installation means discovery could not identify a valid installation through the supported locations. These locations are not a scan of all possible installations.

`status` and `start` also return `process_state`, matching `process_ids`, and `other_process_ids`:

| State | Meaning |
| --- | --- |
| `detected` | A candidate process matches the selected executable path |
| `not_detected` | No candidate process was found in the inspected user/session scope |
| `other_path` | A candidate exists at another path, or exists without matching installation metadata |
| `unknown` | Access restrictions or races prevented reliable detection |

`start` returns `launch_requested`. False means no launch was attempted, including when installation information is missing or the graphical session is unavailable. True means one launch attempt was made, not that a window appeared. An OS launch failure or launcher timeout includes an `error` and is never automatically retried. After a successful launch request, process polling defaults to ten seconds; `--wait-seconds 0..30` controls this bounded polling period, excluding individual OS calls. A polling deadline may leave `process_state=not_detected` without an OS error; that unconfirmed result is not permission to retry.

Exit status is 0 when inspection completed, even when metadata is missing or a launch remains unconfirmed without an OS error. Operational errors return 1 with `ok: false` and an error code/message; invalid CLI arguments return 2 with argparse usage. Keep the structured state when reporting results. No operation configures MCP, changes startup-at-login behavior, closes an application, or grants remote permissions.
