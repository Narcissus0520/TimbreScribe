[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Installer,
    [Parameter(Mandatory = $true)]
    [string]$InstallerManifest,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [string]$Answers,
    [switch]$FailOnIncomplete
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$manualDefinitions = @(
    [pscustomobject]@{id = "install_and_launch"; prompt = "Install and launch the candidate"},
    [pscustomobject]@{id = "mock_transcription"; prompt = "Run and cancel Mock transcription"},
    [pscustomobject]@{id = "basic_pitch_cpu"; prompt = "Run Basic Pitch on CPU"},
    [pscustomobject]@{id = "project_save_reopen"; prompt = "Save and reopen a project"},
    [pscustomobject]@{id = "professional_exports"; prompt = "Export MusicXML, MXL, MIDI, SVG, PNG, and PDF"},
    [pscustomobject]@{id = "project_association"; prompt = "Open a .timbrescribe file through its association"},
    [pscustomobject]@{id = "upgrade_preserves_settings_projects"; prompt = "Upgrade and preserve settings/projects"},
    [pscustomobject]@{id = "uninstall_preserves_projects"; prompt = "Uninstall without deleting projects"},
    [pscustomobject]@{id = "optional_models_absent"; prompt = "Use core features with optional models absent"},
    [pscustomobject]@{id = "offline_core_workflow"; prompt = "Use core workflow with network unavailable"},
    [pscustomobject]@{id = "keyboard_only_workflow"; prompt = "Complete the documented keyboard-only workflow"},
    [pscustomobject]@{id = "narrator_labels_and_order"; prompt = "Review labels and focus order with Narrator"},
    [pscustomobject]@{id = "light_and_dark_themes"; prompt = "Review both light and dark themes"},
    [pscustomobject]@{id = "crash_diagnostics_review"; prompt = "Review a redacted crash diagnostic archive"},
    [pscustomobject]@{id = "cache_cleanup_scope"; prompt = "Confirm cache cleanup preserves projects/settings/models"}
)
$displayDefinitions = @(
    foreach ($displayClass in @("1920x1080", "high-dpi")) {
        foreach ($scale in @(100, 150, 200)) {
            [pscustomobject]@{
                display_class = $displayClass
                scale_percent = $scale
                prompt = "Review $displayClass physical display at $scale percent scaling"
            }
        }
    }
)

function Assert-SafeNote {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Note,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if ($Note.Length -gt 500) {
        throw "$Label exceeds 500 characters."
    }
    if ($Note -match "(?i)([A-Za-z]:\\|\\\\|bearer|password|secret|token|api[_-]?key|hf_|sk-)") {
        throw "$Label contains a path or secret-like text; replace it with a defect reference."
    }
}

function Read-CheckResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Identifier,
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    while ($true) {
        $choice = (Read-Host "$Prompt [p=pass, f=fail, n=not run]").Trim().ToLowerInvariant()
        $status = switch ($choice) {
            "p" { "pass" }
            "f" { "fail" }
            "n" { "not_run" }
            default { $null }
        }
        if ($null -eq $status) {
            Write-Host "Enter p, f, or n."
            continue
        }
        $note = ""
        if ($status -ne "pass") {
            $note = (Read-Host "Optional public defect reference/note (no paths, names, or secrets)").Trim()
            Assert-SafeNote -Note $note -Label "$Identifier note"
        }
        return [pscustomobject]@{id = $Identifier; status = $status; notes = $note}
    }
}

function Read-DisplayResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DisplayClass,
        [Parameter(Mandatory = $true)]
        [int]$ScalePercent,
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    $record = Read-CheckResult -Identifier "$DisplayClass-$ScalePercent" -Prompt $Prompt
    return [pscustomobject]@{
        display_class = $DisplayClass
        scale_percent = $ScalePercent
        status = $record.status
        notes = $record.notes
    }
}

function Read-NonnegativeInteger {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    while ($true) {
        $value = 0
        $text = Read-Host $Prompt
        if ([int]::TryParse($text, [ref]$value) -and $value -ge 0) {
            return $value
        }
        Write-Host "Enter a whole number greater than or equal to zero."
    }
}

function Convert-AnswerChecks {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$InputChecks,
        [Parameter(Mandatory = $true)]
        [object[]]$Definitions
    )

    $expected = @($Definitions | ForEach-Object { [string]$_.id })
    $actual = @($InputChecks | ForEach-Object { [string]$_.id })
    if (@($actual | Sort-Object -Unique).Count -ne $actual.Count) {
        throw "The answer file contains duplicated manual check IDs."
    }
    if (@(Compare-Object ($expected | Sort-Object) ($actual | Sort-Object)).Count -ne 0) {
        throw "The answer file must contain every protocol-v1 manual check exactly once."
    }
    return @(
        foreach ($definition in $Definitions) {
            $answer = $InputChecks | Where-Object { $_.id -eq $definition.id } | Select-Object -First 1
            $status = [string]$answer.status
            if ($status -notin @("pass", "fail", "not_run")) {
                throw "Manual check '$($definition.id)' has an invalid status."
            }
            $note = [string]$answer.notes
            Assert-SafeNote -Note $note -Label "$($definition.id) note"
            [pscustomobject]@{id = [string]$definition.id; status = $status; notes = $note}
        }
    )
}

function Convert-AnswerDisplays {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$InputChecks,
        [Parameter(Mandatory = $true)]
        [object[]]$Definitions
    )

    $actualKeys = @($InputChecks | ForEach-Object { "$($_.display_class)-$($_.scale_percent)" })
    $expectedKeys = @($Definitions | ForEach-Object { "$($_.display_class)-$($_.scale_percent)" })
    if (@($actualKeys | Sort-Object -Unique).Count -ne $actualKeys.Count) {
        throw "The answer file contains duplicated display checks."
    }
    if (@(Compare-Object ($expectedKeys | Sort-Object) ($actualKeys | Sort-Object)).Count -ne 0) {
        throw "The answer file must contain the complete protocol-v1 display matrix."
    }
    return @(
        foreach ($definition in $Definitions) {
            $answer = $InputChecks | Where-Object {
                $_.display_class -eq $definition.display_class -and
                [int]$_.scale_percent -eq [int]$definition.scale_percent
            } | Select-Object -First 1
            $status = [string]$answer.status
            if ($status -notin @("pass", "fail", "not_run")) {
                throw "Display check '$($definition.display_class)-$($definition.scale_percent)' has an invalid status."
            }
            $note = [string]$answer.notes
            Assert-SafeNote -Note $note -Label "display check note"
            [pscustomobject]@{
                display_class = [string]$definition.display_class
                scale_percent = [int]$definition.scale_percent
                status = $status
                notes = $note
            }
        }
    )
}

function Get-ExternalToolNames {
    $toolNames = @(
        "python", "python3", "py", "pip", "pip3", "uv", "git", "ffmpeg", "ffprobe",
        "qmake", "qmake6", "windeployqt"
    )
    $resolved = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )
    foreach ($toolName in $toolNames) {
        $commands = @(Get-Command -Name "$toolName.exe" -CommandType Application -All -ErrorAction SilentlyContinue)
        foreach ($command in $commands) {
            $source = [string]$command.Source
            if ($source -notmatch "(?i)\\Microsoft\\WindowsApps\\") {
                $null = $resolved.Add($toolName)
            }
        }
    }
    return @($resolved | Sort-Object)
}

function Get-DevelopmentEnvironmentVariableNames {
    $names = @(
        "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONHOME", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT",
        "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"
    )
    return @(
        $names | Where-Object {
            -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_))
        } | Sort-Object
    )
}

function Write-AtomicUtf8Json {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Value,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $resolved = [System.IO.Path]::GetFullPath($Destination)
    $parent = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $temporary = "$resolved.tmp.$([guid]::NewGuid().ToString('N'))"
    try {
        $json = ($Value | ConvertTo-Json -Depth 8) + [Environment]::NewLine
        [System.IO.File]::WriteAllText($temporary, $json, [System.Text.UTF8Encoding]::new($false))
        if (Test-Path -LiteralPath $resolved -PathType Leaf) {
            [System.IO.File]::Replace($temporary, $resolved, $null)
        }
        else {
            [System.IO.File]::Move($temporary, $resolved)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Windows x64 is required for release acceptance."
}
$installerPath = [System.IO.Path]::GetFullPath($Installer)
$manifestPath = [System.IO.Path]::GetFullPath($InstallerManifest)
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Installer not found."
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Installer manifest not found."
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([int]$manifest.schema_version -ne 1) {
    throw "Unsupported installer manifest schema."
}
$installerItem = Get-Item -LiteralPath $installerPath
$installerHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($installerItem.Name -ne [string]$manifest.installer) {
    throw "Installer name does not match installer-manifest.json."
}
if ($installerItem.Length -ne [long]$manifest.installer_size) {
    throw "Installer size does not match installer-manifest.json."
}
if ($installerHash -ne ([string]$manifest.installer_sha256).ToLowerInvariant()) {
    throw "Installer SHA-256 does not match installer-manifest.json."
}
if ([string]$manifest.release_manifest_sha256 -notmatch "^[0-9a-fA-F]{64}$") {
    throw "Installer manifest has an invalid release-manifest SHA-256."
}

if ($null -eq ("TimbreScribeDisplayProbe" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class TimbreScribeDisplayProbe {
    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")]
    public static extern uint GetDpiForSystem();
}
"@
}

$os = Get-CimInstance Win32_OperatingSystem
$buildNumber = [int]$os.BuildNumber
$windowsFamily = if ($buildNumber -ge 22000) { "Windows 11" } else { "Windows 10" }
$clientOperatingSystem = [int]$os.ProductType -eq 1
$externalTools = @(Get-ExternalToolNames)
$developmentVariables = @(Get-DevelopmentEnvironmentVariableNames)
$pythonRegistryPresent = @(
    "Registry::HKEY_CURRENT_USER\Software\Python\PythonCore",
    "Registry::HKEY_LOCAL_MACHINE\Software\Python\PythonCore",
    "Registry::HKEY_LOCAL_MACHINE\Software\WOW6432Node\Python\PythonCore"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$architecture = [string]$os.OSArchitecture
$cleanToolchain = (
    $clientOperatingSystem -and
    $architecture.Contains("64") -and
    $externalTools.Count -eq 0 -and
    $developmentVariables.Count -eq 0 -and
    $null -eq $pythonRegistryPresent
)
$systemDpi = try { [TimbreScribeDisplayProbe]::GetDpiForSystem() } catch { 96 }
$currentDisplay = [ordered]@{
    width = [TimbreScribeDisplayProbe]::GetSystemMetrics(0)
    height = [TimbreScribeDisplayProbe]::GetSystemMetrics(1)
    system_scale_percent = [int][Math]::Round(($systemDpi / 96.0) * 100.0)
}

if ([string]::IsNullOrWhiteSpace($Answers)) {
    Write-Host "Record only checks you personally completed against this exact candidate."
    Write-Host "Do not enter usernames, computer names, paths, media titles, tokens, or secrets."
    $manualChecks = @(
        foreach ($definition in $manualDefinitions) {
            Read-CheckResult -Identifier $definition.id -Prompt $definition.prompt
        }
    )
    $displayChecks = @(
        foreach ($definition in $displayDefinitions) {
            Read-DisplayResult `
                -DisplayClass $definition.display_class `
                -ScalePercent $definition.scale_percent `
                -Prompt $definition.prompt
        }
    )
    $p0DefectCount = Read-NonnegativeInteger -Prompt "Open P0 defect count"
    $p1DefectCount = Read-NonnegativeInteger -Prompt "Open P1 defect count"
    $operatorAffirmation = (Read-Host "Type YES to affirm these are your completed observations") -ceq "YES"
}
else {
    $answersPath = [System.IO.Path]::GetFullPath($Answers)
    if (-not (Test-Path -LiteralPath $answersPath -PathType Leaf)) {
        throw "Answer file not found."
    }
    $answerData = Get-Content -LiteralPath $answersPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$answerData.schema_version -ne 1) {
        throw "Unsupported answer schema version."
    }
    $manualChecks = @(Convert-AnswerChecks -InputChecks @($answerData.manual_checks) -Definitions $manualDefinitions)
    $displayChecks = @(Convert-AnswerDisplays -InputChecks @($answerData.display_checks) -Definitions $displayDefinitions)
    $p0DefectCount = [int]$answerData.p0_defect_count
    $p1DefectCount = [int]$answerData.p1_defect_count
    if ($p0DefectCount -lt 0 -or $p1DefectCount -lt 0) {
        throw "Defect counts cannot be negative."
    }
    if ($answerData.operator_affirmation -isnot [bool]) {
        throw "operator_affirmation must be a JSON boolean."
    }
    $operatorAffirmation = [bool]$answerData.operator_affirmation
}

$allManualPassed = @($manualChecks | Where-Object { $_.status -ne "pass" }).Count -eq 0
$anyDisplayPassed = @($displayChecks | Where-Object { $_.status -eq "pass" }).Count -gt 0
$passed = (
    $cleanToolchain -and
    $allManualPassed -and
    $anyDisplayPassed -and
    $p0DefectCount -eq 0 -and
    $p1DefectCount -eq 0 -and
    $operatorAffirmation
)
$evidence = [ordered]@{
    schema_version = 1
    application = "TimbreScribe"
    evidence_type = "windows-client-manual-acceptance"
    recorded_at_utc = [DateTime]::UtcNow.ToString("o")
    candidate = [ordered]@{
        application_version = [string]$manifest.application_version
        installer_name = $installerItem.Name
        installer_sha256 = $installerHash
        installer_size = [long]$installerItem.Length
        inno_setup_version = [string]$manifest.inno_setup_version
        release_manifest_sha256 = ([string]$manifest.release_manifest_sha256).ToLowerInvariant()
        signing_status = [string]$manifest.signing_status
    }
    environment = [ordered]@{
        windows_family = $windowsFamily
        client_operating_system = $clientOperatingSystem
        version = [string]$os.Version
        build = [string]$os.BuildNumber
        architecture = $architecture
        clean_toolchain = $cleanToolchain
        resolved_external_tools = $externalTools
        development_environment_variables = $developmentVariables
        python_registry_present = $null -ne $pythonRegistryPresent
        powershell_version = $PSVersionTable.PSVersion.ToString()
        current_display = $currentDisplay
    }
    manual_checks = $manualChecks
    display_checks = $displayChecks
    p0_defect_count = $p0DefectCount
    p1_defect_count = $p1DefectCount
    operator_affirmation = $operatorAffirmation
    passed = $passed
}
Write-AtomicUtf8Json -Value $evidence -Destination $Output
Write-Output "Windows client acceptance evidence recorded. passed=$($passed.ToString().ToLowerInvariant())"
if ($FailOnIncomplete -and -not $passed) {
    exit 2
}
