[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Files,
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[0-9A-Fa-f]{40}$")]
    [string]$CertificateThumbprint,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [string]$SignToolExecutable,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [ValidateSet("CurrentUser", "LocalMachine")]
    [string]$CertificateStoreLocation = "CurrentUser",
    [string]$InstallerManifest
)

$ErrorActionPreference = "Stop"

function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $algorithm = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $algorithm.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Write-AtomicUtf8Json([object]$Value, [string]$Path) {
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $directory = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $temporary = Join-Path $directory ("." + (Split-Path -Leaf $resolved) + ".tmp." + [guid]::NewGuid().ToString("N"))
    try {
        $json = ($Value | ConvertTo-Json -Depth 8) + "`n"
        [System.IO.File]::WriteAllText($temporary, $json, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $resolved -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Resolve-SignTool([string]$Requested) {
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $resolved = [System.IO.Path]::GetFullPath($Requested)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "SignTool.exe was not found at the requested path."
        }
        return $resolved
    }
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $kitRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitRoot -PathType Container) {
        $candidate = Get-ChildItem -Path (Join-Path $kitRoot "*\x64\signtool.exe") -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($null -ne $candidate) {
            return $candidate.FullName
        }
    }
    throw "SignTool.exe was not found. Install the Windows SDK or pass -SignToolExecutable."
}

function Test-AllowedArtifactName([string]$Name) {
    if ($Name -in @("TimbreScribe.exe", "TimbreScribeWorker.exe")) {
        return $true
    }
    return $Name -match '^TimbreScribe-[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?-windows-x64-setup\.exe$'
}

if (-not [uri]::IsWellFormedUriString($TimestampUrl, [System.UriKind]::Absolute)) {
    throw "TimestampUrl must be an absolute URI."
}
$timestampUri = [uri]$TimestampUrl
if ($timestampUri.Scheme -notin @("http", "https")) {
    throw "TimestampUrl must use HTTP or HTTPS."
}

$thumbprint = $CertificateThumbprint.ToUpperInvariant()
$storePath = "Cert:\$CertificateStoreLocation\My\$thumbprint"
$certificate = Get-Item -LiteralPath $storePath -ErrorAction SilentlyContinue
if ($null -eq $certificate) {
    throw "The selected code-signing certificate was not found in $CertificateStoreLocation\\My."
}
if (-not $certificate.HasPrivateKey) {
    throw "The selected certificate has no accessible private key."
}
$now = Get-Date
if ($certificate.NotBefore -gt $now -or $certificate.NotAfter -le $now) {
    throw "The selected certificate is not currently valid."
}
$codeSigningOid = "1.3.6.1.5.5.7.3.3"
if ($certificate.EnhancedKeyUsageList.ObjectId.Value -notcontains $codeSigningOid) {
    throw "The selected certificate is not valid for code signing."
}

$resolvedFiles = @()
foreach ($file in $Files) {
    $resolved = [System.IO.Path]::GetFullPath($file)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "Signing input was not found: $resolved"
    }
    if (-not (Test-AllowedArtifactName (Split-Path -Leaf $resolved))) {
        throw "Refusing to sign a file outside the TimbreScribe first-party allowlist."
    }
    $resolvedFiles += $resolved
}
if ($resolvedFiles.Count -eq 0 -or ($resolvedFiles | Select-Object -Unique).Count -ne $resolvedFiles.Count) {
    throw "At least one unique signing input is required."
}
if (-not [string]::IsNullOrWhiteSpace($InstallerManifest)) {
    if ($resolvedFiles.Count -ne 1 -or (Split-Path -Leaf $resolvedFiles[0]) -notmatch '-setup\.exe$') {
        throw "-InstallerManifest is valid only when signing one TimbreScribe installer."
    }
}

$signTool = Resolve-SignTool $SignToolExecutable
$fileRecords = @()
foreach ($file in $resolvedFiles) {
    $arguments = @("sign", "/sha1", $thumbprint, "/s", "My")
    if ($CertificateStoreLocation -eq "LocalMachine") {
        $arguments += "/sm"
    }
    $arguments += @(
        "/fd", "SHA256",
        "/tr", $TimestampUrl,
        "/td", "SHA256",
        "/d", "TimbreScribe",
        "/du", "https://github.com/Narcissus0520/TimbreScribe",
        $file
    )
    & $signTool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Authenticode signing failed for $(Split-Path -Leaf $file)."
    }
    & $signTool verify /pa /all /tw $file
    if ($LASTEXITCODE -ne 0) {
        throw "Authenticode verification failed for $(Split-Path -Leaf $file)."
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $file
    if ($signature.Status -ne "Valid") {
        throw "Windows reported a non-valid Authenticode signature for $(Split-Path -Leaf $file)."
    }
    if ($null -eq $signature.SignerCertificate -or $signature.SignerCertificate.Thumbprint -ne $thumbprint) {
        throw "The artifact was not signed by the explicitly selected certificate."
    }
    if ($null -eq $signature.TimeStamperCertificate) {
        throw "The Authenticode signature has no trusted timestamp."
    }
    $fileRecords += [ordered]@{
        name = Split-Path -Leaf $file
        sha256 = Get-Sha256 $file
        size = (Get-Item -LiteralPath $file).Length
        signature_status = "valid"
        timestamped = $true
    }
}

$evidence = [ordered]@{
    schema_version = 1
    application = "TimbreScribe"
    evidence_type = "authenticode-signing"
    certificate = [ordered]@{
        thumbprint = $thumbprint.ToLowerInvariant()
        subject = $certificate.Subject
        issuer = $certificate.Issuer
        not_before_utc = $certificate.NotBefore.ToUniversalTime().ToString("o")
        not_after_utc = $certificate.NotAfter.ToUniversalTime().ToString("o")
    }
    timestamp_url = $TimestampUrl
    files = $fileRecords
}
Write-AtomicUtf8Json $evidence $Output

if (-not [string]::IsNullOrWhiteSpace($InstallerManifest)) {
    $manifestPath = [System.IO.Path]::GetFullPath($InstallerManifest)
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Installer manifest was not found."
    }
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    $installer = $resolvedFiles[0]
    if ([int]$manifest.schema_version -ne 1 -or [string]$manifest.installer -ne (Split-Path -Leaf $installer)) {
        throw "Installer manifest does not identify the signed installer."
    }
    $manifest.installer_sha256 = Get-Sha256 $installer
    $manifest.installer_size = (Get-Item -LiteralPath $installer).Length
    $manifest.signing_status = "authenticode-timestamped"
    $manifest | Add-Member -NotePropertyName signing_certificate_thumbprint -NotePropertyValue $thumbprint.ToLowerInvariant() -Force
    $manifest | Add-Member -NotePropertyName signing_evidence_sha256 -NotePropertyValue (Get-Sha256 ([System.IO.Path]::GetFullPath($Output))) -Force
    Write-AtomicUtf8Json $manifest $manifestPath
}

Write-Output "Authenticode signing and verification completed for $($resolvedFiles.Count) artifact(s)."
