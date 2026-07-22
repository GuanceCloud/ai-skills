[CmdletBinding()]
param(
    [string[]]$Skill,
    [switch]$All,
    [ValidateSet('codex','claude','opencode','pi','gemini','copilot','cursor','amp','agents')][string]$Agent,
    [ValidateSet('user','project')][string]$Scope = 'user',
    [string]$Dest,
    [Alias('project-dir')][string]$ProjectDir,
    [switch]$Force,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Fail([string]$Message) { throw "uninstall.ps1: $Message" }
function Get-Sha256Hex([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}

if ($All -and $Skill) { Fail '-All cannot be combined with -Skill' }
if (-not $Dest -and -not $Agent) {
    if (-not [Environment]::UserInteractive) { Fail '-Agent is required in non-interactive mode' }
    $agents = @('codex','claude','opencode','pi','gemini','copilot','cursor','amp','agents')
    for ($i=0; $i -lt $agents.Count; $i++) { Write-Host "  $($i+1)) $($agents[$i])" }
    $choice = 0
    if (-not [int]::TryParse((Read-Host 'Select an agent'), [ref]$choice) -or $choice -lt 1 -or $choice -gt $agents.Count) { Fail 'invalid agent selection' }
    $Agent = $agents[$choice-1]
}

if ($Scope -eq 'project') {
    if (-not $ProjectDir) {
        try { $ProjectDir = (& git rev-parse --show-toplevel 2>$null).Trim() } catch { $ProjectDir = (Get-Location).Path }
        if (-not $ProjectDir) { $ProjectDir = (Get-Location).Path }
    }
    $ProjectDir = [IO.Path]::GetFullPath($ProjectDir)
}

if ($Dest) { $destRoot = [IO.Path]::GetFullPath($Dest) }
elseif ($Scope -eq 'user') {
    $relative = @{
        codex='.codex/skills'; claude='.claude/skills'; opencode='.config/opencode/skills'; pi='.pi/agent/skills';
        gemini='.gemini/skills'; copilot='.copilot/skills'; cursor='.cursor/skills'; amp='.config/agents/skills'; agents='.agents/skills'
    }[$Agent]
    $destRoot = Join-Path $HOME $relative
} else {
    $relative = @{
        codex='.agents/skills'; agents='.agents/skills'; amp='.agents/skills'; claude='.claude/skills'; opencode='.opencode/skills';
        pi='.pi/skills'; gemini='.gemini/skills'; copilot='.github/skills'; cursor='.cursor/skills'
    }[$Agent]
    $destRoot = Join-Path $ProjectDir $relative
}
if (-not (Test-Path -LiteralPath $destRoot -PathType Container)) { Fail "skill destination does not exist: $destRoot" }
$destRoot = [IO.Path]::GetFullPath($destRoot)

$managed = @(Get-ChildItem -LiteralPath $destRoot -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.skill-install.json') } | Select-Object -ExpandProperty Name | Sort-Object)
if ($All) { $Skill = $managed }
elseif (-not $Skill) {
    if ($managed.Count -eq 0) { Fail "no managed skills found in $destRoot" }
    if (-not [Environment]::UserInteractive) { Fail '-Skill or -All is required in non-interactive mode' }
    for ($i=0; $i -lt $managed.Count; $i++) { Write-Host "  $($i+1)) $($managed[$i])" }
    $choice = 0
    if (-not [int]::TryParse((Read-Host 'Select a skill to uninstall'), [ref]$choice) -or $choice -lt 1 -or $choice -gt $managed.Count) { Fail 'invalid skill selection' }
    $Skill = @($managed[$choice-1])
}
if (-not $Skill -or $Skill.Count -eq 0) { Fail "no managed skills found in $destRoot" }

function Test-LocalModification([string]$Installed) {
    $checksumFile = Join-Path $Installed '.skill-files.sha256'
    $listFile = Join-Path $Installed '.skill-files.list'
    if (-not (Test-Path $checksumFile) -or -not (Test-Path $listFile)) { return $true }
    foreach ($line in [IO.File]::ReadAllLines($checksumFile)) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { return $true }
        $path = Join-Path $Installed $Matches[2]
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $true }
        if ((Get-Sha256Hex $path) -ne $Matches[1]) { return $true }
    }
    $excluded = @('.skill-install.json','.skill-files.sha256','.skill-files.list','.skill-setup.tsv')
    $current = @(Get-ChildItem -LiteralPath $Installed -File -Recurse | ForEach-Object {
        $relative = $_.FullName.Substring($Installed.Length).TrimStart('\','/').Replace('\','/')
        if ($excluded -notcontains $relative) { $relative }
    } | Sort-Object)
    $expected = @([IO.File]::ReadAllLines($listFile) | Sort-Object)
    return @(Compare-Object $expected $current).Count -ne 0
}

$modified = New-Object System.Collections.Generic.List[string]
foreach ($name in $Skill) {
    if ($name -notmatch '^[A-Za-z0-9_-]+$') { Fail "invalid skill name: $name" }
    $installed = Join-Path $destRoot $name
    if (-not (Test-Path -LiteralPath $installed -PathType Container)) { Fail "skill is not installed: $name" }
    if (((Get-Item -LiteralPath $installed).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Fail "refusing to remove a reparse-point skill directory: $installed" }
    if (-not (Test-Path -LiteralPath (Join-Path $installed '.skill-install.json') -PathType Leaf)) { Fail "refusing to remove unmanaged directory: $installed" }
    if (Test-LocalModification $installed) {
        if (-not $Force) { Fail "$name has local modifications; pass -Force to back it up and uninstall it" }
        $modified.Add($name)
    }
}

Write-Host "Uninstall destination: $destRoot"
Write-Host "Skills: $($Skill -join ', ')"
if (-not $Yes) {
    if (-not [Environment]::UserInteractive) { Fail 'confirmation requires an interactive terminal; pass -Yes' }
    if ((Read-Host 'Remove these managed skills? [y/N]') -notmatch '^(y|yes)$') { Fail 'cancelled' }
}

$txn = Join-Path $destRoot ('.ai-skills-uninstall-txn-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($txn) | Out-Null
$moved = New-Object System.Collections.Generic.List[string]
try {
    foreach ($name in $Skill) {
        Move-Item -LiteralPath (Join-Path $destRoot $name) -Destination (Join-Path $txn $name)
        $moved.Add($name)
    }
    $backupRoot = $null
    if ($modified.Count -gt 0) {
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')
        if ($Scope -eq 'project') { $backupRoot = Join-Path $ProjectDir ".ai-skills/backups/$stamp" }
        else {
            $dataRoot = $env:XDG_DATA_HOME
            if (-not $dataRoot) { $dataRoot = Join-Path $HOME '.local/share' }
            $backupRoot = Join-Path $dataRoot "ai-skills/backups/$stamp"
        }
        [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
        foreach ($name in $modified) { Copy-Item -LiteralPath (Join-Path $txn $name) -Destination (Join-Path $backupRoot $name) -Recurse }
    }
} catch {
    foreach ($name in $moved) {
        $source = Join-Path $txn $name
        if (Test-Path $source) { Move-Item -LiteralPath $source -Destination (Join-Path $destRoot $name) }
    }
    throw
}

Remove-Item -LiteralPath $txn -Recurse -Force
Write-Host "Uninstalled successfully: $($Skill -join ', ')"
if ($backupRoot) { Write-Host "Modified skills were backed up to: $backupRoot" }
else { Write-Host 'No backup was created for unmodified skills.' }
