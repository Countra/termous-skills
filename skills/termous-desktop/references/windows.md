# Windows Installation Discovery, Running State, and Launch

Use this workflow locally with Windows PowerShell 5.1 or PowerShell 7, never on a remote SSH host. It uses built-in system capabilities without installing modules, reading user configuration, or scanning ports. First confirm that the client's execution tool runs on the user's Windows computer.

## Installation contract

The fixed subkey is `Software\Termous\Install`, accessed through `Registry64`. HKCU refers to the Windows account running the query; HKLM describes a machine-wide installation. Prefer HKCU when both records are valid.

| Field | Requirement |
| --- | --- |
| `SchemaVersion` | Integer `1`; `0` or a missing value indicates an incomplete record |
| `AppId` | `dev.termous.app` |
| `DisplayName` | Display name, normally `Termous` |
| `DisplayVersion` | Nonempty installed version |
| `InstallLocation` | Absolute installation directory |
| `ExecutablePath` | Absolute path to `Termous.exe` in that directory, without arguments or surrounding quotes |

Registry metadata locates the application; it is neither launch authorization nor signature verification. Fall back to HKLM when the current-user record is missing, incomplete, or points to a missing executable. Report permission errors instead of treating them as absence. Older versions and portable directories may have no record. Upgrades briefly remove the old record and register the new installation only after installation finishes.

## Query installation information

Load the following function, then call `Get-TermousInstallation`. An empty result means no valid record was found. The output contains only application metadata.

```powershell
function Get-TermousInstallation {
    $ErrorActionPreference = 'Stop'
    foreach ($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
        $baseKey = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, [Microsoft.Win32.RegistryView]::Registry64)
        try {
            $key = $baseKey.OpenSubKey('Software\Termous\Install')
            if ($null -eq $key) { continue }
            try {
                $schema = $key.GetValue('SchemaVersion')
                $appId = $key.GetValue('AppId')
                if ($schema -isnot [int] -or $schema -ne 1 -or
                    $appId -isnot [string] -or $appId -cne 'dev.termous.app') { continue }
                $directory = $key.GetValue('InstallLocation')
                $executable = $key.GetValue('ExecutablePath')
                $version = $key.GetValue('DisplayVersion')
                if ($directory -isnot [string] -or $executable -isnot [string] -or
                    $version -isnot [string] -or [string]::IsNullOrWhiteSpace($version)) { continue }
                $absolute = '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$))'
                if ($directory -notmatch $absolute -or $executable -notmatch $absolute) { continue }
                try {
                    # Use filesystem path operations so stale drive letters do not trigger PowerShell drive errors.
                    $directory = [IO.Path]::GetFullPath($directory)
                    $expected = [IO.Path]::GetFullPath([IO.Path]::Combine($directory, 'Termous.exe'))
                    $executable = [IO.Path]::GetFullPath($executable)
                } catch [ArgumentException] { continue }
                catch [NotSupportedException] { continue }
                catch [IO.PathTooLongException] { continue }
                if ($executable -ine $expected -or
                    -not (Test-Path -LiteralPath $expected -PathType Leaf)) { continue }
                return [pscustomobject]@{
                    AppId = 'dev.termous.app'
                    Version = $version
                    InstallLocation = $directory
                    ExecutablePath = $expected
                    RegistryHive = $hive.ToString()
                }
            } finally { $key.Dispose() }
        } finally { $baseKey.Dispose() }
    }
}
```

## Check running state

Load the installation function and the following function, then call `Get-TermousDesktopState`. Inspect only processes named Termous in the current Windows session and verify their executable paths. Do not output command lines, environment variables, or information about other applications.

```powershell
function Get-TermousDesktopState {
    $ErrorActionPreference = 'Stop'
    $installation = Get-TermousInstallation
    if ($null -eq $installation) {
        return [pscustomobject]@{ Installation = $null; ProcessState = 'installation_unavailable'; ProcessIds = @() }
    }
    $current = [Diagnostics.Process]::GetCurrentProcess()
    try { $sessionID = $current.SessionId } finally { $current.Dispose() }
    $processIDs = [Collections.Generic.List[int]]::new()
    $unknown = $false
    $otherPath = $false
    try { $candidates = [Diagnostics.Process]::GetProcessesByName('Termous') }
    catch { throw "Cannot enumerate Termous processes; running state is unknown: $($_.Exception.Message)" }
    foreach ($candidate in $candidates) {
        try {
            if ($candidate.HasExited -or $candidate.SessionId -ne $sessionID) { continue }
            $executable = $candidate.MainModule.FileName
            if ([string]::IsNullOrWhiteSpace($executable)) { $unknown = $true; continue }
            if ([IO.Path]::GetFullPath($executable) -ieq $installation.ExecutablePath) {
                $processIDs.Add($candidate.Id)
            } else { $otherPath = $true }
        } catch {
            # Access restrictions or exit races do not establish that the application is not running.
            $unknown = $true
        } finally { $candidate.Dispose() }
    }
    $state = 'not_detected'
    if ($processIDs.Count -gt 0) { $state = 'detected' }
    elseif ($unknown) { $state = 'unknown' }
    elseif ($otherPath) { $state = 'other_path' }
    return [pscustomobject]@{
        Installation = $installation
        ProcessState = $state
        ProcessIds = @($processIDs.ToArray())
    }
}
```

| ProcessState | Meaning and next action |
| --- | --- |
| `detected` | A process matches the current session and installation path; do not launch again |
| `not_detected` | No target process was found during this check; launch only when requested |
| `other_path` | A same-name process in the current session uses another path; report the mismatch without launching another version automatically |
| `unknown` | Candidate process information could not be read reliably; report the unknown state without elevating or terminating processes |
| `installation_unavailable` | No valid installation record exists; this does not establish that all Termous instances are stopped |

Electron may have several processes using the same path; the PID list does not count windows or sessions. Process presence does not prove main-window visibility or MCP connectivity. Minimized or tray-hidden instances may also be `detected`. When checking MCP, use only the client's existing authorized connection; do not scan dynamic ports.

## Launch when requested

Load the first two functions and the following function, then call `Start-TermousDesktop`. Follow the client's execution approval requirements; do not ask again solely because the user has already explicitly requested a launch. The function accepts no executable path, arguments, or elevation options. It launches only the just-validated installation, at most once per call.

```powershell
function Start-TermousDesktop {
    $ErrorActionPreference = 'Stop'
    $before = Get-TermousDesktopState
    if ($before.ProcessState -ne 'not_detected') {
        return [pscustomobject]@{ LaunchRequested = $false; State = $before }
    }
    $installation = $before.Installation
    $started = Start-Process -FilePath $installation.ExecutablePath -WorkingDirectory $installation.InstallLocation -PassThru -ErrorAction Stop
    if ($null -ne $started) { $started.Dispose() }
    # Check for a matching process up to ten times, one second apart; never relaunch to resolve uncertainty.
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        Start-Sleep -Milliseconds 1000
        try { $after = Get-TermousDesktopState }
        catch { throw "Termous launch was requested, but the state check failed. Do not retry the launch automatically: $($_.Exception.Message)" }
        if ($null -eq $after.Installation -or $after.Installation.ExecutablePath -ine $installation.ExecutablePath) {
            throw 'Termous launch was requested, but installation information changed. Do not retry the launch automatically.'
        }
        if ($after.ProcessState -ne 'not_detected') { break }
    }
    return [pscustomobject]@{ LaunchRequested = $true; State = $after }
}
```

- `LaunchRequested=false`: explain why no launch occurred using the returned state; `detected` means a process already exists.
- `LaunchRequested=true` with `State.ProcessState=detected`: a launch was requested and a matching process was observed. Do not promise window visibility or MCP readiness.
- A requested launch followed by `not_detected` or `unknown/other_path`: report that the launch could not be confirmed and describe the current state. Do not launch again or terminate processes.
- If `Start-Process` fails, report the failure. Do not automatically switch paths, elevate, change execution policy, or reinstall. Never execute a registry value as a shell command string.

This Skill does not provide shutdown, restart, upgrades, startup-at-login changes, MCP configuration, or remote command execution. For subsequent remote work, use the appropriate domain Skill with its existing permissions and approval workflow.
