[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Installer
)

$ErrorActionPreference = "Stop"
$installerPath = [System.IO.Path]::GetFullPath($Installer)
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Installer not found: $installerPath"
}
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("TimbreScribe-installer-smoke-" + [guid]::NewGuid().ToString("N"))
$installRoot = Join-Path $temporaryRoot "installed"
$externalProjects = Join-Path $temporaryRoot "user-projects"
$sentinel = Join-Path $externalProjects "preserve.timbrescribe"
$report = Join-Path $temporaryRoot "smoke.json"
$isolatedLocalAppData = Join-Path $temporaryRoot "local-app-data"
$preservedSettings = Join-Path $isolatedLocalAppData "TimbreScribe\settings.json"
$originalLocalAppData = $env:LOCALAPPDATA
New-Item -ItemType Directory -Path $externalProjects -Force | Out-Null
[System.IO.File]::WriteAllText($sentinel, "preserve", [System.Text.UTF8Encoding]::new($false))
$env:LOCALAPPDATA = $isolatedLocalAppData

try {
    $install = Start-Process -FilePath $installerPath -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=$installRoot"
    ) -Wait -PassThru -WindowStyle Hidden
    if ($install.ExitCode -ne 0) { throw "Silent install failed with exit code $($install.ExitCode)." }
    $application = Join-Path $installRoot "TimbreScribe.exe"
    if (-not (Test-Path -LiteralPath $application -PathType Leaf)) { throw "Installed GUI is missing." }
    $smoke = Start-Process -FilePath $application -ArgumentList @("--smoke-test", "--report", $report) -Wait -PassThru -WindowStyle Hidden
    if ($smoke.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report -PathType Leaf)) {
        throw "Installed application smoke test failed."
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $preservedSettings) -Force | Out-Null
    [System.IO.File]::WriteAllText($preservedSettings, '{"upgrade":"preserve"}', [System.Text.UTF8Encoding]::new($false))
    $upgrade = Start-Process -FilePath $installerPath -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=$installRoot"
    ) -Wait -PassThru -WindowStyle Hidden
    if ($upgrade.ExitCode -ne 0) { throw "Clean in-place upgrade failed." }
    if ((Get-Content -Raw -LiteralPath $preservedSettings) -ne '{"upgrade":"preserve"}') {
        throw "Upgrade did not preserve application settings."
    }
    $association = (Get-ItemProperty -LiteralPath "Registry::HKEY_CURRENT_USER\Software\Classes\.timbrescribe" -ErrorAction Stop).'(default)'
    if ($association -ne "TimbreScribe.Project") { throw "Project file association was not registered." }
    $uninstaller = Join-Path $installRoot "unins000.exe"
    $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART"
    ) -Wait -PassThru -WindowStyle Hidden
    if ($uninstall.ExitCode -ne 0) { throw "Silent uninstall failed." }
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
        throw "Uninstall removed a user project outside the application directory."
    }
    if (-not (Test-Path -LiteralPath $preservedSettings -PathType Leaf)) {
        throw "Silent uninstall removed settings without user consent."
    }
    if (Test-Path -LiteralPath "Registry::HKEY_CURRENT_USER\Software\Classes\.timbrescribe") {
        throw "Project file association remained after uninstall."
    }
    Write-Output "Installer install/smoke/association/uninstall preservation test passed."
}
finally {
    $env:LOCALAPPDATA = $originalLocalAppData
    $safeTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $resolvedTemporary = [System.IO.Path]::GetFullPath($temporaryRoot)
    if ($resolvedTemporary.StartsWith($safeTemp, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedTemporary)) {
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force -ErrorAction SilentlyContinue
    }
}
