[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FfmpegDirectory,
    [string]$OutputRoot,
    [string]$UvExecutable,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot "work\release"
}
$releaseRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$safeRoot = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot "work"))
if (-not $releaseRoot.StartsWith($safeRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release output must remain below the repository work directory: $safeRoot"
}

if ([string]::IsNullOrWhiteSpace($UvExecutable)) {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $uvCommand) {
        $UvExecutable = $uvCommand.Source
    }
    else {
        $repositoryUv = Join-Path $repositoryRoot "work\uv-bin\uv.exe"
        if (Test-Path -LiteralPath $repositoryUv -PathType Leaf) {
            $UvExecutable = $repositoryUv
        }
    }
}
if ([string]::IsNullOrWhiteSpace($UvExecutable) -or -not (Test-Path -LiteralPath $UvExecutable -PathType Leaf)) {
    throw "uv.exe was not found; pass -UvExecutable with the approved uv 0.11.29 executable."
}

$distRoot = Join-Path $releaseRoot "dist"
$buildRoot = Join-Path $releaseRoot "build"
$artifactRoot = Join-Path $releaseRoot "artifacts"
if ($Clean) {
    foreach ($target in @($distRoot, $buildRoot, $artifactRoot)) {
        $resolvedTarget = [System.IO.Path]::GetFullPath($target)
        if (-not $resolvedTarget.StartsWith($releaseRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a release path outside the validated root: $resolvedTarget"
        }
        if (Test-Path -LiteralPath $resolvedTarget) {
            Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
        }
    }
}
New-Item -ItemType Directory -Path $distRoot, $buildRoot, $artifactRoot -Force | Out-Null

$ffmpegBin = [System.IO.Path]::GetFullPath($FfmpegDirectory)
$ffmpegExe = Join-Path $ffmpegBin "ffmpeg.exe"
$ffprobeExe = Join-Path $ffmpegBin "ffprobe.exe"
if (-not (Test-Path -LiteralPath $ffmpegExe -PathType Leaf) -or -not (Test-Path -LiteralPath $ffprobeExe -PathType Leaf)) {
    throw "FfmpegDirectory must contain ffmpeg.exe and ffprobe.exe."
}
$expectedFfmpeg = "abe4f6dc7ca6d807c9492e56f96db9030d7c5faba942254aa00d4474042048d4"
$expectedFfprobe = "f1b2041be46d1d2e1e2f77f950de6fe624cdf65b692c04f880b6ce81e99e03a1"
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ffmpegExe).Hash.ToLowerInvariant() -ne $expectedFfmpeg) {
    throw "The selected ffmpeg.exe does not match the approved release hash."
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ffprobeExe).Hash.ToLowerInvariant() -ne $expectedFfprobe) {
    throw "The selected ffprobe.exe does not match the approved release hash."
}
$ffmpegRoot = Split-Path -Parent $ffmpegBin
$ffmpegLicense = @("LICENSE.txt", "LICENSE") |
    ForEach-Object { Join-Path $ffmpegRoot $_ } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($ffmpegLicense)) {
    throw "The approved FFmpeg distribution license was not found beside its bin directory."
}

Push-Location $repositoryRoot
try {
    & $UvExecutable lock --check
    if ($LASTEXITCODE -ne 0) { throw "uv lock --check failed." }
    & $UvExecutable run python tools/verify_basic_pitch.py
    if ($LASTEXITCODE -ne 0) { throw "The approved Basic Pitch wheel/model verification failed." }
    $env:PYTHONHASHSEED = "0"
    $env:SOURCE_DATE_EPOCH = (& git show -s --format=%ct HEAD).Trim()
    $buildCommand = "uv run pyinstaller --noconfirm --clean --distpath work/release/dist --workpath work/release/build packaging/pyinstaller/TimbreScribe.spec"
    & $UvExecutable run pyinstaller --noconfirm --clean --distpath $distRoot --workpath $buildRoot packaging/pyinstaller/TimbreScribe.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

    $bundle = Join-Path $distRoot "TimbreScribe"
    if (-not (Test-Path -LiteralPath (Join-Path $bundle "TimbreScribe.exe") -PathType Leaf)) {
        throw "PyInstaller did not create the GUI executable."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $bundle "TimbreScribeWorker.exe") -PathType Leaf)) {
        throw "PyInstaller did not create the worker executable."
    }
    $bundleFfmpeg = Join-Path $bundle "ffmpeg"
    New-Item -ItemType Directory -Path $bundleFfmpeg -Force | Out-Null
    Copy-Item -Path (Join-Path $ffmpegBin "*") -Destination $bundleFfmpeg -Recurse -Force

    $manifestDirectory = Join-Path $bundle "manifests"
    New-Item -ItemType Directory -Path $manifestDirectory -Force | Out-Null
    Copy-Item -LiteralPath "src/timbrescribe/infrastructure/ffmpeg/reference_manifest.json" -Destination (Join-Path $manifestDirectory "ffmpeg-reference-manifest.json")
    Copy-Item -LiteralPath "src/timbrescribe/infrastructure/basic_pitch/manifest.json" -Destination (Join-Path $manifestDirectory "basic-pitch-manifest.json")
    Copy-Item -LiteralPath "src/timbrescribe/infrastructure/muscriptor/manifest.json" -Destination (Join-Path $manifestDirectory "muscriptor-manifest.json") -ErrorAction Stop
    Copy-Item -LiteralPath "src/timbrescribe/infrastructure/assistant/model_manifest.json" -Destination (Join-Path $manifestDirectory "assistant-model-manifest.json")
    Copy-Item -LiteralPath "packaging/third_party/ffmpeg/CONFIGURATION.txt" -Destination $manifestDirectory

    & $UvExecutable run python packaging/scripts/stage_release_licenses.py --bundle $bundle --repository $repositoryRoot --ffmpeg-license $ffmpegLicense
    if ($LASTEXITCODE -ne 0) { throw "License staging failed." }
    $releaseManifest = Join-Path $manifestDirectory "release-manifest.json"
    & $UvExecutable run python packaging/scripts/generate_release_manifest.py --bundle $bundle --output $releaseManifest --repository $repositoryRoot --build-command $buildCommand
    if ($LASTEXITCODE -ne 0) { throw "Release manifest generation failed." }
    $archive = Join-Path $artifactRoot "TimbreScribe-0.9.0-windows-x64-onedir.zip"
    & $UvExecutable run python packaging/scripts/create_release_archive.py --bundle $bundle --output $archive --source-date-epoch $env:SOURCE_DATE_EPOCH
    if ($LASTEXITCODE -ne 0) { throw "Release archive generation failed." }
    Write-Output "Staged onedir: $bundle"
    Write-Output "Deterministic archive: $archive"
}
finally {
    Pop-Location
}
