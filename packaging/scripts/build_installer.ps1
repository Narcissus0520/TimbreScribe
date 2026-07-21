[CmdletBinding()]
param(
    [string]$BundleDirectory,
    [string]$OutputDirectory,
    [string]$IsccExecutable,
    [string]$AppVersion = "0.9.0"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
if ([string]::IsNullOrWhiteSpace($BundleDirectory)) {
    $BundleDirectory = Join-Path $repositoryRoot "work\release\dist\TimbreScribe"
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot "work\release\artifacts"
}
$bundle = [System.IO.Path]::GetFullPath($BundleDirectory)
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath (Join-Path $bundle "manifests\release-manifest.json") -PathType Leaf)) {
    throw "Build the verified onedir bundle before compiling the installer."
}

if ([string]::IsNullOrWhiteSpace($IsccExecutable)) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe")
    )
    $IsccExecutable = $candidates |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($IsccExecutable) -or -not (Test-Path -LiteralPath $IsccExecutable -PathType Leaf)) {
    throw "Inno Setup 7 ISCC.exe was not found; pass -IsccExecutable explicitly."
}
$innoRegistry = Get-ItemProperty -LiteralPath "Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1" -ErrorAction SilentlyContinue
$innoVersion = if ($null -ne $innoRegistry) { $innoRegistry.DisplayVersion } else { (Get-Item -LiteralPath $IsccExecutable).VersionInfo.ProductVersion }
if ($innoVersion -ne "7.0.2") {
    throw "The release compiler must be Inno Setup 7.0.2; found '$innoVersion'."
}
New-Item -ItemType Directory -Path $output -Force | Out-Null

$script = Join-Path $repositoryRoot "packaging\windows\TimbreScribe.iss"
& $IsccExecutable "/DSourceDir=$bundle" "/DOutputDir=$output" "/DAppVersion=$AppVersion" $script
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
$installer = Join-Path $output "TimbreScribe-$AppVersion-windows-x64-setup.exe"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "The expected installer was not produced: $installer"
}
$releaseManifest = Join-Path $bundle "manifests\release-manifest.json"
$metadata = [ordered]@{
    schema_version = 1
    application_version = $AppVersion
    installer = (Split-Path -Leaf $installer)
    installer_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
    installer_size = (Get-Item -LiteralPath $installer).Length
    inno_setup_version = $innoVersion
    release_manifest_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseManifest).Hash.ToLowerInvariant()
    signing_status = "unsigned-not-authorized"
    build_command = "ISCC.exe /DSourceDir=<onedir> /DOutputDir=<artifacts> /DAppVersion=$AppVersion packaging/windows/TimbreScribe.iss"
}
$metadataPath = Join-Path $output "installer-manifest.json"
$json = ($metadata | ConvertTo-Json -Depth 4) + "`n"
[System.IO.File]::WriteAllText($metadataPath, $json, [System.Text.UTF8Encoding]::new($false))
Write-Output "Installer: $installer"
Write-Output "Installer metadata: $metadataPath"
