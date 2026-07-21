param(
    [switch]$VerifyOnly,
    [ValidateSet("cpu", "cuda126")]
    [string]$TorchRuntime = "cpu"
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
    if (-not $VerifyOnly -and $TorchRuntime -eq "cuda126") {
        $cudaWheel = "https://download-r2.pytorch.org/whl/cu126/torch-2.13.0%2Bcu126-cp311-cp311-win_amd64.whl#sha256=8095729db14e7fd5178a39676fdd679208eff4041407ea34e3d898336c90f5c5"
        & $uvExecutable pip install --python $managedPython --reinstall --no-deps $cudaWheel
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install the pinned PyTorch CUDA 12.6 runtime."
        }
    }
    $verificationArguments = @("tools/verify_muscriptor.py")
    if ($TorchRuntime -eq "cuda126") {
        $verificationArguments += "--require-cuda126"
    }
    & $managedPython @verificationArguments
    if ($LASTEXITCODE -ne 0) {
        throw "MuScriptor code-runtime verification failed."
    }
    Write-Host "Use the in-app license gate and model manager for any gated weight download."
}
finally {
    Pop-Location
}
