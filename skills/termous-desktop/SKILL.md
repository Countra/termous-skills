---
name: termous-desktop
description: Discover the installed Termous desktop application on Windows, read its version and executable path, check whether its processes are running, or launch it when requested. Use the external client's local PowerShell capability; this workflow works before Termous or its MCP server starts. Not for remote SSH processes, Docker, installation, upgrades, or arbitrary local application management.
---

# Termous Desktop

Discover the local Termous installation on Windows, check its running state, and launch it when requested. Use the external AI client's local PowerShell execution capability; Termous MCP is not required.

## Choose an operation

Read the [Windows discovery and launch workflow](references/windows.md), then choose the operation that matches the request:

- **Version, installation directory, or executable path:** call `Get-TermousInstallation` to query installation metadata only.
- **Running state:** call `Get-TermousDesktopState` to validate the installation record and process paths in the current Windows session.
- **Launch:** call `Start-TermousDesktop` only when the user explicitly requests a launch or authorizes launching if not already running. A query alone does not authorize a launch.

The reference code only defines functions; loading it does not launch the application. Use the client's existing local execution tool to load and call the required functions in the same PowerShell session. Do not assume a client-specific tool name, change the execution policy, or require administrator privileges.

## Results and boundaries

- Currently supports the fixed discovery entry provided by official Windows installers. Query the 64-bit registry view, preferring the current user's HKCU record over the machine-wide HKLM record. Do not scan disks, guess default directories, or modify the registry.
- Older installations, manually moved executables, or upgrades in progress may lack a valid record. Report that no valid installation information was found; do not conclude that Termous is not installed or download, install, or repair registry entries automatically.
- `detected` means a process with a matching executable path exists. It does not prove window visibility, application health, or MCP readiness. The installed version may differ from the version of an already-running process.
- Do not launch again when a matching process exists. Report other-path processes, access restrictions, or an unconfirmed launch explicitly; do not terminate processes, repeatedly restart, or elevate automatically.
- Inspect only the current Windows session and do not launch on behalf of other logged-in users. Explain this scope if the user asks about another account.
- If the built-in Termous AI assistant has no local execution tool, never send these PowerShell commands to a remote SSH tool. A responsive built-in assistant indicates that its own instance is running, but does not establish installation metadata.
- Do not use these commands on other platforms or guess discovery locations that have not been defined. If local execution is unavailable, explain the limitation and provide instructions for opening Termous manually.

For remote work after launch, use the corresponding Termous MCP Skill. If MCP remains unavailable, ask the user to check the service and client configuration in Termous MCP settings. Do not read tokens, guess dynamic ports, or change connection settings automatically.
