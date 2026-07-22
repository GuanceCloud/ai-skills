[CmdletBinding()]
param(
    [Alias('base-url')][string]$BaseUrl,
    [string[]]$Skill,
    [switch]$All,
    [ValidateSet('codex','claude','opencode','pi','gemini','copilot','cursor','amp','agents')][string]$Agent,
    [ValidateSet('user','project')][string]$Scope = 'user',
    [string]$Dest,
    [Alias('project-dir')][string]$ProjectDir,
    [string]$Version = 'latest',
    [switch]$Upgrade,
    [switch]$Force,
    [Alias('run-setup')][switch]$RunSetup,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Fail([string]$Message) { throw "install.ps1: $Message" }
function Get-Sha256Hex([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}
if ([string]::IsNullOrWhiteSpace($BaseUrl)) { Fail '-BaseUrl is required' }
$BaseUrl = $BaseUrl.TrimEnd('/')
if ($BaseUrl -notmatch '^https?://') { Fail '-BaseUrl must start with http:// or https://' }
if ($All -and $Skill) { Fail '-All cannot be combined with -Skill' }
if ($Version -ne 'latest' -and ($Version -notmatch '^[0-9a-fA-F]{40}$')) { Fail '-Version must be a full 40-character commit SHA' }

$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("ai-skills-install-" + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($TempRoot) | Out-Null
try {
    $indexRelative = 'skills-index.tsv'
    if ($Version -ne 'latest') { $indexRelative = "versions/$Version/skills-index.tsv" }
    $indexFile = Join-Path $TempRoot 'skills-index.tsv'
    Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/$indexRelative" -OutFile $indexFile
    $entries = @{}
    foreach ($line in [IO.File]::ReadAllLines($indexFile)) {
        if ($line.StartsWith('#') -or [string]::IsNullOrWhiteSpace($line)) { continue }
        $fields = $line.Split("`t")
        if ($fields.Count -lt 6) { Fail 'invalid skills-index.tsv' }
        $entries[$fields[0]] = [pscustomobject]@{ Name=$fields[0]; Version=$fields[1]; TarPath=$fields[2]; TarHash=$fields[3]; ZipPath=$fields[4]; ZipHash=$fields[5] }
    }
    if ($entries.Count -eq 0) { Fail 'the release index contains no skills' }

    if ($All) { $Skill = @($entries.Keys | Sort-Object) }
    elseif (-not $Skill) {
        if (-not [Environment]::UserInteractive) { Fail '-Skill or -All is required in non-interactive mode' }
        $names = @($entries.Keys | Sort-Object)
        for ($i=0; $i -lt $names.Count; $i++) { Write-Host "  $($i+1)) $($names[$i])" }
        $choice = 0
        if (-not [int]::TryParse((Read-Host 'Select a skill'), [ref]$choice) -or $choice -lt 1 -or $choice -gt $names.Count) { Fail 'invalid skill selection' }
        $Skill = @($names[$choice-1])
    }

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
    [IO.Directory]::CreateDirectory($destRoot) | Out-Null
    $destRoot = [IO.Path]::GetFullPath($destRoot)

    Write-Host "Install destination: $destRoot"
    Write-Host "Skills: $($Skill -join ', ')"
    if (-not $Yes) {
        if (-not [Environment]::UserInteractive) { Fail 'confirmation requires an interactive terminal; pass -Yes' }
        if ((Read-Host 'Continue? [y/N]') -notmatch '^(y|yes)$') { Fail 'cancelled' }
    }

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
        return (Compare-Object $expected $current).Count -ne 0
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $prepared = Join-Path $TempRoot 'prepared'
    [IO.Directory]::CreateDirectory($prepared) | Out-Null
    $forceBackups = New-Object System.Collections.Generic.List[string]
    $installNames = New-Object System.Collections.Generic.List[string]
    foreach ($name in $Skill) {
        if (-not $entries.ContainsKey($name)) { Fail "skill is not published: $name" }
        $entry = $entries[$name]
        if ($Version -ne 'latest' -and $entry.Version -ne $Version) { Fail 'release index version does not match -Version' }
        if ($entry.ZipPath.StartsWith('/') -or $entry.ZipPath -match '(^|/)\.\.($|/)' -or $entry.ZipHash -notmatch '^[0-9a-f]{64}$') { Fail "invalid archive metadata for $name" }
        $archive = Join-Path $TempRoot "$name.zip"
        Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/$($entry.ZipPath)" -OutFile $archive
        if ((Get-Sha256Hex $archive) -ne $entry.ZipHash) { Fail "SHA-256 mismatch for $name" }
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            foreach ($item in $zip.Entries) {
                $normalized = $item.FullName.Replace('\','/')
                if (-not $normalized.StartsWith("$name/") -or $normalized -match '(^|/)\.\.($|/)' -or $normalized.StartsWith('/')) { Fail "unsafe archive path for $name" }
            }
        } finally { $zip.Dispose() }
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $prepared)
        $newPath = Join-Path $prepared $name
        if (-not (Test-Path (Join-Path $newPath 'SKILL.md'))) { Fail "archive for $name has no SKILL.md" }
        $installed = Join-Path $destRoot $name
        if (Test-Path $installed) {
            $installedVersion = $null
            try { $installedVersion = (Get-Content (Join-Path $installed '.skill-install.json') -Raw | ConvertFrom-Json).version } catch {}
            $modified = Test-LocalModification $installed
            if ($installedVersion -eq $entry.Version -and -not $modified) {
                Remove-Item -LiteralPath $newPath -Recurse -Force
                Write-Host "Already installed: $name@$($entry.Version)"
                continue
            }
            if (-not $Upgrade) { Fail "$name is already installed; pass -Upgrade" }
            if ($modified) {
                if (-not $Force) { Fail "$name has local modifications; pass -Force to back it up and replace it" }
                $forceBackups.Add($name)
            }
        }
        $metadata = [ordered]@{ schema_version=1; name=$name; version=$entry.Version; archive_sha256=$entry.ZipHash; source="$BaseUrl/$($entry.ZipPath)"; installed_at=[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ') }
        [IO.File]::WriteAllText((Join-Path $newPath '.skill-install.json'), ($metadata | ConvertTo-Json -Compress) + "`n", (New-Object Text.UTF8Encoding($false)))
        $installNames.Add($name)
    }

    $txn = Join-Path $destRoot ('.ai-skills-txn-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($txn) | Out-Null
    $applied = New-Object System.Collections.Generic.List[string]
    try {
        foreach ($name in $installNames) {
            $installed = Join-Path $destRoot $name
            if (Test-Path $installed) { Move-Item -LiteralPath $installed -Destination (Join-Path $txn "old-$name") }
            $applied.Add($name)
            Move-Item -LiteralPath (Join-Path $prepared $name) -Destination $installed
        }
        if ($forceBackups.Count -gt 0) {
            $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
            if ($Scope -eq 'project') { $backupRoot = Join-Path $ProjectDir ".ai-skills/backups/$stamp" }
            else {
                $dataRoot = $env:XDG_DATA_HOME
                if (-not $dataRoot) { $dataRoot = Join-Path $HOME '.local/share' }
                $backupRoot = Join-Path $dataRoot "ai-skills/backups/$stamp"
            }
            [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
            foreach ($name in $forceBackups) { Copy-Item -LiteralPath (Join-Path $txn "old-$name") -Destination (Join-Path $backupRoot $name) -Recurse }
            Write-Host "Local modifications backed up to: $backupRoot"
        }
    } catch {
        foreach ($name in $applied) {
            $installed = Join-Path $destRoot $name
            if (Test-Path $installed) { Remove-Item -LiteralPath $installed -Recurse -Force }
            $old = Join-Path $txn "old-$name"
            if (Test-Path $old) { Move-Item -LiteralPath $old -Destination $installed }
        }
        throw
    } finally {
        if (Test-Path $txn) { Remove-Item -LiteralPath $txn -Recurse -Force }
    }

    if ($RunSetup) {
        foreach ($name in $Skill) {
            $setupFile = Join-Path (Join-Path $destRoot $name) '.skill-setup.tsv'
            if (-not (Test-Path $setupFile) -or (Get-Item $setupFile).Length -eq 0) { Write-Host "No setup declared for $name"; continue }
            $executable = $null
            $arguments = New-Object System.Collections.Generic.List[string]
            foreach ($line in [IO.File]::ReadAllLines($setupFile)) {
                $fields = $line.Split("`t", 2)
                if ($fields[0] -eq 'windows-executable') { $executable = $fields[1] }
                elseif ($fields[0] -eq 'windows-arg') { $arguments.Add($fields[1]) }
            }
            if (-not $executable) { Write-Host "No Windows setup declared for $name"; continue }
            Write-Host "Setup command for $name`: $executable $($arguments -join ' ')"
            if (-not $Yes -and (Read-Host 'Run setup? [y/N]') -notmatch '^(y|yes)$') { continue }
            Push-Location (Join-Path $destRoot $name)
            try { & $executable @arguments; if ($LASTEXITCODE -ne 0) { Fail "setup failed for $name" } } finally { Pop-Location }
        }
    }
    Write-Host "Installed successfully into $destRoot"
} finally {
    if (Test-Path $TempRoot) { Remove-Item -LiteralPath $TempRoot -Recurse -Force }
}
