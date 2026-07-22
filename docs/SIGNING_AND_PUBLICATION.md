# Windows signing and publication

> **Dormant optional procedure:** ADR 0021 supersedes this workflow for the current project scope.
> Do not obtain a certificate, sign artifacts, create a tag, or publish a Release unless a future
> explicit user instruction reopens the scope. This document is retained only as tested technical
> reference.

TimbreScribe uses Authenticode for its two first-party executables and the Inno Setup installer.
The FFmpeg, Qt, Python, and other third-party binaries retain their upstream signatures and must not
be re-signed as TimbreScribe. GitHub credentials and Hugging Face tokens are not code-signing
certificates.

## Required inputs

- A publicly trusted Authenticode code-signing certificate with an accessible private key and the
  Code Signing EKU (`1.3.6.1.5.5.7.3.3`). The certificate may be exposed by a hardware token or
  cloud key provider through the Windows `CurrentUser\My` or `LocalMachine\My` certificate store.
- Windows SDK `SignTool.exe`. `sign_windows_artifacts.ps1` finds the newest x64 Windows 10 SDK copy,
  or accepts an explicit path.
- An RFC 3161 timestamp service allowed by the certificate issuer. The default is the DigiCert
  endpoint documented in Microsoft's SignTool examples.
- Passed, privacy-minimized Windows 10 and Windows 11 operator records created against the final
  signed installer. Evidence for an unsigned installer is invalid after signing changes its hash.
- An authenticated GitHub CLI session with release permission. Do not store a certificate password,
  PFX payload, token, or private key in the repository, evidence JSON, command history, or logs.

## Build and sign the candidate

Start from a clean release commit and the verified FFmpeg distribution. The examples assume the
certificate is already available through the current user's certificate store:

```powershell
$thumbprint = "<40-hex-certificate-thumbprint>"

./packaging/scripts/build_onedir.ps1 `
  -FfmpegDirectory $env:TIMBRESCRIBE_FFMPEG_DIR `
  -Clean

./packaging/scripts/sign_windows_artifacts.ps1 `
  -Files @(
    ".\work\release\dist\TimbreScribe\TimbreScribe.exe",
    ".\work\release\dist\TimbreScribe\TimbreScribeWorker.exe"
  ) `
  -CertificateThumbprint $thumbprint `
  -Output ".\work\release\dist\TimbreScribe\manifests\authenticode-bundle.json"
```

Signing changes the bundle. Regenerate the file manifest and deterministic ZIP before compiling the
installer:

```powershell
$bundle = ".\work\release\dist\TimbreScribe"
$releaseManifest = "$bundle\manifests\release-manifest.json"
$buildCommand = "uv run pyinstaller --noconfirm --clean --distpath work/release/dist --workpath work/release/build packaging/pyinstaller/TimbreScribe.spec"

uv run python packaging/scripts/generate_release_manifest.py `
  --bundle $bundle `
  --output $releaseManifest `
  --repository . `
  --build-command $buildCommand

$sourceDateEpoch = (Get-Content -Raw $releaseManifest | ConvertFrom-Json).source_date_epoch
uv run python packaging/scripts/create_release_archive.py `
  --bundle $bundle `
  --output ".\work\release\artifacts\TimbreScribe-0.9.0-windows-x64-onedir.zip" `
  --source-date-epoch $sourceDateEpoch

./packaging/scripts/build_installer.ps1 `
  -SigningStatus bundle-authenticode-installer-unsigned

./packaging/scripts/sign_windows_artifacts.ps1 `
  -Files ".\work\release\artifacts\TimbreScribe-0.9.0-windows-x64-setup.exe" `
  -CertificateThumbprint $thumbprint `
  -Output ".\work\release\artifacts\authenticode-installer.json" `
  -InstallerManifest ".\work\release\artifacts\installer-manifest.json"

./packaging/scripts/test_installer.ps1 `
  -Installer ".\work\release\artifacts\TimbreScribe-0.9.0-windows-x64-setup.exe"
```

The signing script fails closed if the certificate is missing, expired, lacks a private key or code
signing EKU, if SignTool reports any warning/failure, if the signer differs from the selected
thumbprint, or if a trusted timestamp is absent. Its filename allowlist prevents accidental signing
of third-party executables.

## Clean-client acceptance after signing

Copy the signed installer, updated `installer-manifest.json`, recorder, and answer template to the
clean clients. Follow `CLEAN_MACHINE_VALIDATION.md` on Windows 10 and Windows 11. The records must
identify `signing_status` as `authenticode-timestamped` and bind the final signed installer hash.

After both raw records return, stage the exact public asset set:

```powershell
uv run python packaging/scripts/finalize_windows_release.py `
  --archive .\work\release\artifacts\TimbreScribe-0.9.0-windows-x64-onedir.zip `
  --installer .\work\release\artifacts\TimbreScribe-0.9.0-windows-x64-setup.exe `
  --installer-manifest .\work\release\artifacts\installer-manifest.json `
  --release-manifest .\work\release\dist\TimbreScribe\manifests\release-manifest.json `
  --bundle-signing .\work\release\dist\TimbreScribe\manifests\authenticode-bundle.json `
  --installer-signing .\work\release\artifacts\authenticode-installer.json `
  --acceptance-record .\evidence\windows-10-acceptance.json `
  --acceptance-record .\evidence\windows-11-acceptance.json `
  --output-directory .\work\release\public
```

The finalizer independently revalidates the raw records and requires the complete client/display
matrix. It also proves the ZIP matches `release-manifest.json`, both first-party executables and the
installer share the selected timestamped certificate, every candidate hash is consistent, and the
acceptance records target that exact signed installer. It then creates `release-assets.json` and
`SHA256SUMS.txt` in a new staging directory; it never publishes by itself.

## Publish and verify

Create an annotated tag at the `git_commit` recorded by `release-assets.json`, push the tag, and use
`gh release create --verify-tag`. Version `0.9.0` is a prerelease, not a stable v1 claim. Upload every
file from `work/release/public`, the release notes, user guide, troubleshooting guide, model/license
notices, and source supplied automatically by GitHub. After publication, download all assets into a
fresh directory, verify `SHA256SUMS.txt`, inspect Authenticode again, and rerun the installed smoke
test. Do not mark the release latest/stable until every v1 gate in `RELEASE_CHECKLIST.md` passes.
