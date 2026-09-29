param([string]$ReferencePath)
$ErrorActionPreference = 'Stop'
$source = [IO.File]::ReadAllText($ReferencePath)
$blocks = [regex]::Matches($source, '(?s)```powershell\r?\n(.*?)```')
if ($blocks.Count -ne 3) { throw 'Unexpected workflow code blocks' }
$code = ($blocks | ForEach-Object { $_.Groups[1].Value }) -join "`n"
$replacements = @{
    '[Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, [Microsoft.Win32.RegistryView]::Registry64)' = '(Open-FixtureRegistry $hive)'
    '[Diagnostics.Process]::GetCurrentProcess()' = '(Get-FixtureCurrentProcess)'
    "[Diagnostics.Process]::GetProcessesByName('Termous')" = '(Get-FixtureCandidates)'
}
foreach ($entry in $replacements.GetEnumerator()) {
    if (($code.Split(@($entry.Key), [StringSplitOptions]::None)).Count -ne 2) { throw 'System boundary changed: review fixture' }
    $code = $code.Replace($entry.Key, $entry.Value)
}
if ($code -match 'RegistryKey|\[Diagnostics\.Process\]') { throw 'Real system access is forbidden' }

function Assert-Equal($actual, $expected) {
    if ($actual -cne $expected) { throw "Expected '$expected', got '$actual'" }
}

function Add-Disposable($value) {
    $value | Add-Member NoteProperty Disposed $false
    $value | Add-Member ScriptMethod Dispose { $this.Disposed = $true }
    $script:handles.Add($value)
    return $value
}

function Open-FixtureRegistry($hive) {
    if ($script:denyRegistry) { throw 'Fixture access denied' }
    $values = $script:records[$hive.ToString()]
    $key = $null
    if ($null -ne $values) {
        $key = Add-Disposable ([pscustomobject]@{ Values = $values })
        $key | Add-Member ScriptMethod GetValue { param($name) return $this.Values[$name] }
    }
    $baseKey = Add-Disposable ([pscustomobject]@{ Key = $key })
    $baseKey | Add-Member ScriptMethod OpenSubKey {
        param($name)
        Assert-Equal $name 'Software\Termous\Install'
        return $this.Key
    }
    return $baseKey
}

function Test-Path {
    param($LiteralPath, $PathType)
    Assert-Equal $PathType 'Leaf'
    if ($script:denyFileAccess) { throw 'Fixture file access denied' }
    return $LiteralPath -in $script:files
}

function Get-FixtureCurrentProcess {
    return Add-Disposable ([pscustomobject]@{ SessionId = 42 })
}

function Get-FixtureCandidates {
    if ($script:denyEnumeration) { throw 'Fixture enumeration failed' }
    foreach ($item in $script:candidates) {
        $candidate = Add-Disposable ([pscustomobject]@{
            Id = $item.Id; SessionId = $item.SessionId; HasExited = [bool]$item.Exited
        })
        if ($item.Denied) {
            $candidate | Add-Member ScriptProperty MainModule { throw 'Fixture path access denied' }
        } else {
            $candidate | Add-Member NoteProperty MainModule ([pscustomobject]@{ FileName = $item.Path })
        }
        $candidate
    }
}

function Start-Process {
    param($FilePath, $WorkingDirectory, [switch]$PassThru, $ErrorAction)
    $script:launches++
    Assert-Equal $FilePath $script:expectedLaunch.ExecutablePath
    Assert-Equal $WorkingDirectory $script:expectedLaunch.InstallLocation
    if ($script:failLaunch) { throw 'Fixture launch failed' }
    if ($script:appearAfterLaunch) {
        $script:candidates = @(@{ Id = 100; SessionId = 42; Path = $FilePath })
    }
    return Add-Disposable ([pscustomobject]@{ Id = 100 })
}

function Start-Sleep {
    param($Milliseconds)
    Assert-Equal $Milliseconds 1000
    $script:waits++
    if ($script:changeAfterLaunch) { $script:records.CurrentUser = $null }
    if ($script:denyAfterLaunch) { $script:denyRegistry = $true }
}

function Reset-Fixture {
    $directory = 'C:\Program Files\Termous ' + [char]0x7528
    $script:user = @{
        SchemaVersion = 1; AppId = 'dev.termous.app'; DisplayVersion = '1.0.0'
        InstallLocation = $directory; ExecutablePath = "$directory\Termous.exe"
    }
    $script:machine = @{
        SchemaVersion = 1; AppId = 'dev.termous.app'; DisplayVersion = '2.0.0'
        InstallLocation = 'C:\TermousAll'; ExecutablePath = 'C:\TermousAll\Termous.exe'
    }
    $script:records = @{ CurrentUser = $script:user; LocalMachine = $script:machine }
    $script:expectedLaunch = $script:user
    $script:files = @($script:user.ExecutablePath, $script:machine.ExecutablePath)
    $script:handles = [Collections.Generic.List[object]]::new()
    $script:candidates = @()
    $script:launches = 0
    $script:waits = 0
    $script:appearAfterLaunch = $true
    $script:denyRegistry = $false
    $script:denyFileAccess = $false
    $script:denyEnumeration = $false
    $script:failLaunch = $false
    $script:changeAfterLaunch = $false
    $script:denyAfterLaunch = $false
}

function Assert-Disposed {
    Assert-Equal @($script:handles | Where-Object { -not $_.Disposed }).Count 0
}

function Assert-Throws($operation, $expected) {
    $message = ''
    try { & $operation | Out-Null } catch { $message = $_.Exception.Message }
    if ($message -notlike "*$expected*") { throw "Expected failure containing '$expected', got '$message'" }
}

# 只加载实际文档中的函数；所有系统读取、进程启动和等待都被内存替身接管。
Reset-Fixture
. ([scriptblock]::Create($code))
Assert-Equal $script:launches 0
Assert-Equal (Get-TermousInstallation).RegistryHive 'CurrentUser'
Assert-Equal (Get-TermousDesktopState).ProcessState 'not_detected'
Assert-Equal $script:launches 0
Assert-Disposed

foreach ($mutation in @(
    @{ SchemaVersion = 0 }, @{ SchemaVersion = '1' }, @{ SchemaVersion = 2 },
    @{ AppId = 'other.app' }, @{ DisplayVersion = '' }, @{ InstallLocation = 'C:relative' },
    @{ AppId = @('dev.termous.app', 'dev.termous.app') },
    @{ InstallLocation = "C:\Invalid$([char]0)Path" },
    @{ ExecutablePath = 'C:\Other\Termous.exe' }, @{ ExecutablePath = @('C:\Other\Termous.exe') }
)) {
    Reset-Fixture
    foreach ($field in $mutation.Keys) { $script:user[$field] = $mutation[$field] }
    Assert-Equal (Get-TermousInstallation).RegistryHive 'LocalMachine'
    Assert-Disposed
}

Reset-Fixture
$script:files = @($script:machine.ExecutablePath)
Assert-Equal (Get-TermousInstallation).Version '2.0.0'
Assert-Disposed
Reset-Fixture
# 失效记录所在盘符不可用时，仍能发现并启动全机安装。
$script:user.InstallLocation = 'Z:\TermousOld'
$script:user.ExecutablePath = 'Z:\TermousOld\Termous.exe'
$script:expectedLaunch = $script:machine
$result = Start-TermousDesktop
Assert-Equal $result.State.Installation.RegistryHive 'LocalMachine'
Assert-Equal $result.State.ProcessState 'detected'
Assert-Equal $script:launches 1
Assert-Disposed
Reset-Fixture
$script:records = @{}
Assert-Equal (Start-TermousDesktop).State.ProcessState 'installation_unavailable'
Assert-Equal $script:launches 0
Assert-Disposed

foreach ($scenario in @(
    @{ State = 'detected'; Item = @{ Id = 1; SessionId = 42; Path = $script:user.ExecutablePath } },
    @{ State = 'other_path'; Item = @{ Id = 2; SessionId = 42; Path = 'C:\Other\Termous.exe' } },
    @{ State = 'unknown'; Item = @{ Id = 3; SessionId = 42; Denied = $true } }
)) {
    Reset-Fixture
    $script:candidates = @($scenario.Item)
    $result = Start-TermousDesktop
    Assert-Equal $result.State.ProcessState $scenario.State
    Assert-Equal $result.LaunchRequested $false
    Assert-Equal $script:launches 0
    Assert-Disposed
}

Reset-Fixture
$script:candidates = @(@{ Id = 4; SessionId = 99; Path = $script:user.ExecutablePath })
Assert-Equal (Get-TermousDesktopState).ProcessState 'not_detected'
Assert-Disposed
$result = Start-TermousDesktop
Assert-Equal $result.State.ProcessState 'detected'
Assert-Equal $result.LaunchRequested $true
Assert-Equal $script:launches 1
Assert-Equal $script:waits 1
Assert-Disposed

Reset-Fixture
$script:appearAfterLaunch = $false
Assert-Equal (Start-TermousDesktop).State.ProcessState 'not_detected'
Assert-Equal $script:launches 1
Assert-Equal $script:waits 10
Assert-Disposed

Reset-Fixture
$script:denyRegistry = $true
Assert-Throws { Start-TermousDesktop } 'Fixture access denied'
Assert-Equal $script:launches 0
Reset-Fixture
$script:denyFileAccess = $true
Assert-Throws { Start-TermousDesktop } 'Fixture file access denied'
Assert-Equal $script:launches 0
Assert-Disposed
Reset-Fixture
$script:denyEnumeration = $true
Assert-Throws { Start-TermousDesktop } 'Fixture enumeration failed'
Assert-Equal $script:launches 0
Assert-Disposed
Reset-Fixture
$script:failLaunch = $true
Assert-Throws { Start-TermousDesktop } 'Fixture launch failed'
Assert-Equal $script:launches 1
Assert-Disposed

foreach ($failure in @('changeAfterLaunch', 'denyAfterLaunch')) {
    Reset-Fixture
    Set-Variable -Name $failure -Scope Script -Value $true
    Assert-Throws { Start-TermousDesktop } 'Termous'
    Assert-Equal $script:launches 1
    Assert-Disposed
}
Write-Output 'DESKTOP_WORKFLOW_OK'
