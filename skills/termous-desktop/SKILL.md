---
name: termous-desktop
description: Discover the local Termous desktop installation, read available version and path metadata, check whether it is running, or launch it when requested on Windows, macOS, and Linux. Uses a bundled Python standard-library helper through the external client's local execution tool and works before Termous MCP starts. Not for remote SSH processes, installation, upgrades, or managing other applications.
---

# Termous Desktop

Use the bundled [Python helper](scripts/termous_desktop.py) directly. Do not copy code out of Markdown or write a replacement discovery command. Python 3.9 or newer is required; no pip packages are needed. Use an already-installed interpreter (`python` or `py -3` on Windows, usually `python3` on macOS and Linux). If none is available, report that requirement without installing one automatically.

## Commands

Resolve the script relative to this installed Skill, then pass its absolute path to the client's local execution tool. Examples from the Skill directory:

```text
python -B scripts/termous_desktop.py info
python -B scripts/termous_desktop.py status
python -B scripts/termous_desktop.py start
```

- `info` reads installation metadata only.
- `status` checks installation metadata and local processes without launching anything.
- `start` launches at most once, only if a valid installation exists and no matching, conflicting, or inaccessible process prevents a reliable decision. Call it only when the user requests a launch or explicitly authorizes launching if not running.

For a macOS application outside the standard Applications directories or a Linux AppImage without a desktop entry, use the absolute path supplied by the user:

```text
python3 -B scripts/termous_desktop.py status --path "/Applications/Termous.app"
python3 -B scripts/termous_desktop.py start --path "/home/user/Applications/Termous.AppImage"
```

Replace example paths with a known user-provided path; do not guess or scan disks. Windows uses the installer registry record and does not accept `--path`. Read [platform discovery and result semantics](references/platforms.md) when interpreting missing metadata, process states, or a launch result.

## Boundaries

- This workflow requires the external client's local execution capability. Do not send it to SSH or run it on another computer. The built-in Termous assistant cannot use it without a local execution tool.
- Loading the script or using `info`/`status` never launches the application. Follow existing client execution approvals for `start`; an explicit launch request need not be reconfirmed solely by this Skill.
- Registry records, bundle metadata, and filenames locate an installation; they do not verify a signature or authorize execution.
- Process detection does not establish window visibility, application health, MCP readiness, or the version of an already-running process. Minimized and tray-hidden instances still count as running.
- Report unknown states and missing metadata honestly. Do not terminate processes, elevate, alter execution policies, download dependencies, or retry uncertain launches automatically.
- For remote work after launch, use the corresponding Termous MCP Skill and the client's configured authorized connection. Do not read tokens, scan ports, or reconfigure MCP automatically.
