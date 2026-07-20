param(
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -ne $uvCommand) {
    $uvExecutable = $uvCommand.Source
}
else {
    $uvExecutable = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Recurse -Filter uv.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*astral-sh.uv*" } |
        Select-Object -First 1 -ExpandProperty FullName
}
if ([string]::IsNullOrWhiteSpace($uvExecutable)) {
    throw "uv was not found. Install uv and reopen the terminal."
}
Push-Location $repositoryRoot
try {
    if (-not $VerifyOnly) {
        & $uvExecutable sync --frozen --group dev --group muscriptor
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to synchronize the optional MuScriptor code runtime."
        }
    }
    $managedPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $managedPython -PathType Leaf)) {
        throw "The managed Python environment is missing. Run this script without -VerifyOnly."
    }
    & $managedPython tools/verify_muscriptor.py
    if ($LASTEXITCODE -ne 0) {
        throw "MuScriptor code-runtime verification failed."
    }
    Write-Host "Use the in-app license gate and model manager for any gated weight download."
}
finally {
    Pop-Location
}
