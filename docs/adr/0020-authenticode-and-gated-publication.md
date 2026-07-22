# ADR 0020: Authenticode signing and fail-closed public release staging

- Status: Accepted
- Date: 2026-07-22

## Context

The Windows onedir bundle and Inno Setup installer are reproducible, hashed, and tested, but the
existing release-candidate workflow intentionally produces unsigned private artifacts. The user has
now authorized certificate use, public hashes, and publication to GitHub Releases. Authorization
does not provide a signing identity: no local certificate, private key, signing service, or GitHub
Actions signing secret is currently configured.

Authenticode mutates PE files and therefore changes the bundle manifest, ZIP, installer, and every
candidate hash. The clean Win10/Win11 operator evidence must identify the exact signed installer;
evidence for the prior unsigned candidate cannot be reused. Third-party executables must retain
their upstream identity rather than being re-signed as TimbreScribe.

## Decision

TimbreScribe signs only its PyInstaller-generated `TimbreScribe.exe`,
`TimbreScribeWorker.exe`, and its Inno Setup installer. The signer requires an explicitly selected
certificate thumbprint from the Windows certificate store, an accessible private key, a currently
valid Code Signing EKU, SHA-256 file digest, and an RFC 3161 SHA-256 timestamp. It verifies the
Authenticode policy, all embedded signatures, timestamp presence, and exact selected signer before
emitting privacy-safe evidence. The implementation follows Microsoft's documented SignTool
requirements for `/fd`, `/tr`, `/td`, `/pa`, `/all`, and `/tw`.

After bundle signing, release hashes and the deterministic ZIP are regenerated before Inno Setup
compiles the installer. After installer signing, its manifest is atomically rebound to the final
hash and signing evidence. Clean-client evidence is then rerun against that installer.

Public staging fails closed unless all of these agree:

- the two first-party executable signatures and installer signature;
- one explicit certificate thumbprint and trusted timestamps;
- bundle file records, signing evidence, release manifest, and ZIP members;
- installer hash/size, installer manifest, and release-manifest hash;
- original privacy-minimized Win10 and Win11 records and the complete display/accessibility matrix;
- zero P0/P1 defects and explicit operator affirmation.

The staging tool creates public `release-assets.json` and `SHA256SUMS.txt` but performs no network
write. Publication uses an annotated, already-pushed tag plus `gh release create --verify-tag` and
must be followed by an independent download/hash/signature check. GitHub artifact attestations may
supplement this chain later, but do not replace Windows Authenticode trust or product acceptance.

## Consequences

- A trusted certificate or compatible hardware/cloud key provider is a real external prerequisite.
- Signing and timestamping are intentionally nondeterministic finalization steps; the unsigned build
  remains reproducible, while signed outputs are content-addressed and auditable.
- Every signature change, certificate change, or installer rebuild invalidates prior client records.
- Certificate passwords, PFX payloads, private keys, tokens, and absolute operator paths never enter
  repository files or public evidence.
- Version `0.9.0` remains a prerelease. Stable v1 publication still requires all contract gates.

## Rejected alternatives

- **Create a self-signed certificate:** it provides no public Windows trust and preserves reputation
  warnings while creating a misleading appearance of completion.
- **Treat a GitHub/Hugging Face token or GitHub attestation as Authenticode:** these authenticate
  different systems and cannot establish a Windows publisher identity.
- **Re-sign every EXE/DLL in the bundle:** this would falsely present upstream FFmpeg, Qt, Python,
  and other third-party code as publisher-built TimbreScribe binaries.
- **Publish the unsigned candidate and replace it later:** asset replacement weakens provenance and
  leaves existing downloads bound to a different hash.
- **Reuse unsigned-candidate Win10/Win11 evidence:** signing changes the installer bytes and violates
  the versioned evidence protocol's exact-candidate binding.
