# ADR 0021: Private unsigned candidate scope

- Status: Accepted
- Date: 2026-07-22
- Supersedes: ADR 0020 for the current project scope; ADR 0018's final-publication clause

## Context

The repository has a verified private Windows release-candidate workflow and optional fail-closed
Authenticode/publication tooling. The user first authorized signing and public publication, then
explicitly changed the current project scope: no code signing and no public release are required.
No tag or GitHub Release has been created, and the private workflow artifact remains unsigned.

The core product and Windows acceptance work do not inherently require public distribution. The
repository contract requires explicit authorization before an external publication, and it permits
the user to reprioritize milestone scope.

## Decision

Version `0.9.0` remains an internal, private, unsigned release candidate. Do not:

- obtain, create, install, or use a code-signing certificate for this project;
- send a signing request to SignPath or another signing service;
- create or push a release tag;
- create a GitHub Release or publish installer/ZIP hashes as release assets;
- upload the candidate to another public destination.

Continue clean Windows 10/11, physical-display, keyboard-only, and Narrator validation against the
exact unsigned candidate identified by `installer-manifest.json`. The private GitHub Actions artifact
and repository status may retain candidate hashes as internal engineering evidence.

The already-implemented signer and signed-release finalizer stay tested but dormant. They are not a
current requirement, blocker, or implied plan. Reactivating either signing or public publication
requires a new explicit user instruction, a fresh scope review, and candidate-appropriate evidence.

## Consequences

- No certificate, private key, signing account, signing fee, or publisher identity is needed.
- Windows can display an unknown-publisher/reputation warning if the private installer is manually
  copied to another machine; this limitation must remain visible to testers.
- Successful private acceptance proves product behavior for the recorded candidate, not suitability
  for public distribution.
- `v0.9.0` has no public release notes or public download page.
- Source development and staged GitHub pull-request integration continue normally.

## Rejected alternatives

- **Continue signing because the tooling exists:** rejected because implementation availability does
  not override the user's current scope.
- **Publish an unsigned prerelease anyway:** rejected because the user explicitly selected no public
  release.
- **Delete the hardened signing implementation:** rejected because it is isolated, tested, and may be
  useful only if a future instruction deliberately reopens that scope.
