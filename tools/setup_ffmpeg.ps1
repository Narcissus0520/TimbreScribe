param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA "TimbreScribe\components\ffmpeg-n8.1.2-lgpl-shared")
)

$ErrorActionPreference = "Stop"

$ffmpegSetupUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-06-30-13-34/ffmpeg-n8.1.2-21-gce3c09c101-win64-lgpl-shared-8.1.zip"
$ffmpegSetupArchiveHash = "27bcaf58b5140171dfe838a0b365d12c60607d71fc168424456410bad6a834da"
$ffmpegSetupBinaryHash = "abe4f6dc7ca6d807c9492e56f96db9030d7c5faba942254aa00d4474042048d4"
$ffprobeSetupBinaryHash = "f1b2041be46d1d2e1e2f77f950de6fe624cdf65b692c04f880b6ce81e99e03a1"
$ffmpegSetupRoot = [System.IO.Path]::GetFullPath($Destination)
$ffmpegSetupArchive = Join-Path $ffmpegSetupRoot "ffmpeg-reference.zip"

New-Item -ItemType Directory -Path $ffmpegSetupRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $ffmpegSetupArchive -PathType Leaf)) {
    Invoke-WebRequest -Uri $ffmpegSetupUrl -OutFile $ffmpegSetupArchive -UseBasicParsing
}

$actualArchiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ffmpegSetupArchive).Hash.ToLowerInvariant()
if ($actualArchiveHash -ne $ffmpegSetupArchiveHash) {
    throw "FFmpeg archive hash mismatch at $ffmpegSetupArchive"
}

$ffmpegSetupBin = Get-ChildItem -LiteralPath $ffmpegSetupRoot -Filter ffmpeg.exe -File -Recurse |
    Select-Object -First 1 -ExpandProperty DirectoryName
if (-not $ffmpegSetupBin) {
    Expand-Archive -LiteralPath $ffmpegSetupArchive -DestinationPath $ffmpegSetupRoot
    $ffmpegSetupBin = Get-ChildItem -LiteralPath $ffmpegSetupRoot -Filter ffmpeg.exe -File -Recurse |
        Select-Object -First 1 -ExpandProperty DirectoryName
}
if (-not $ffmpegSetupBin) {
    throw "The verified archive did not contain ffmpeg.exe"
}

$ffmpegSetupExe = Join-Path $ffmpegSetupBin "ffmpeg.exe"
$ffprobeSetupExe = Join-Path $ffmpegSetupBin "ffprobe.exe"
if (-not (Test-Path -LiteralPath $ffprobeSetupExe -PathType Leaf)) {
    throw "The verified archive did not contain a sibling ffprobe.exe"
}
$actualFfmpegHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ffmpegSetupExe).Hash.ToLowerInvariant()
$actualFfprobeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ffprobeSetupExe).Hash.ToLowerInvariant()
if ($actualFfmpegHash -ne $ffmpegSetupBinaryHash -or $actualFfprobeHash -ne $ffprobeSetupBinaryHash) {
    throw "Extracted FFmpeg binary hash mismatch"
}

$ffmpegVersionOutput = & $ffmpegSetupExe -version 2>&1
if ($LASTEXITCODE -ne 0 -or $ffmpegVersionOutput[0] -notmatch "n8\.1\.2-21-gce3c09c101-20260630") {
    throw "Extracted FFmpeg version mismatch"
}
$ffmpegVersionText = $ffmpegVersionOutput -join "`n"
if ($ffmpegVersionText -match "--enable-nonfree" -or $ffmpegVersionText -notmatch "--disable-static") {
    throw "Extracted FFmpeg configure flags do not match the approved shared LGPL reference"
}

$env:TIMBRESCRIBE_FFMPEG_DIR = $ffmpegSetupBin
if ($env:GITHUB_PATH) {
    Add-Content -LiteralPath $env:GITHUB_PATH -Value $ffmpegSetupBin
}
if ($env:GITHUB_ENV) {
    Add-Content -LiteralPath $env:GITHUB_ENV -Value "TIMBRESCRIBE_FFMPEG_DIR=$ffmpegSetupBin"
}
Write-Output "Verified FFmpeg reference bin: $ffmpegSetupBin"
