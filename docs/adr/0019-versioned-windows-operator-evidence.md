# ADR 0019: Versioned Windows operator acceptance evidence

- Status: Accepted
- Date: 2026-07-22

## Context

Phase 8 automation proves the frozen executable, worker protocol, packaged model, hashes, high-DPI
geometry, UI Automation semantics, installer lifecycle, and data-preservation boundaries. It cannot
prove that a Windows 10/11 client was pristine, that Narrator spoke useful labels in a usable order,
or that a person completed keyboard and physical-display workflows. Free-form checklist notes do
not reliably bind observations to one candidate and can accidentally include paths or secrets.

## Decision

Use a versioned JSON operator-evidence protocol. A Windows PowerShell 5.1 recorder runs without
Python on the clean client, verifies the installer against `installer-manifest.json`, derives the
Windows family from the build, requires a client x64 OS, and records whether Python/uv/Git/FFmpeg/Qt
tools, development environment variables, or Python registry entries are present. It collects an
explicit pass/fail/not-run result for every host, accessibility, diagnostic, and display check. It
does not infer a human result from UI Automation and cannot pass without operator affirmation and
zero open P0/P1 defects.

Keep names, hostnames, absolute paths, media/project titles, tokens, and secrets out of the record.
Notes are optional, bounded, and reject path/secret-like strings. Record only OS/build,
architecture, tool/variable names, display metrics, candidate hashes, result IDs, and counts.

Aggregate records with a dependency-free Python validator in the managed repository environment.
The final matrix requires the exact same candidate on clean Windows 10 and Windows 11 clients, all
host checks passed on both, and 1920x1080 plus high-DPI physical-display passes at 100%, 150%, and
200%. The two hosts may divide display coverage. The validator recomputes record pass conditions,
rejects unknown or missing protocol fields, and emits its own hash-bound summary.

## Alternatives

- Treat GitHub hosted Windows as the client matrix: rejected because the runner currently uses
  Windows Server and has a development toolchain.
- Treat UI Automation as Narrator acceptance: rejected because provider exposure does not prove
  speech content, order, or non-visual score usability.
- Commit screenshots, machine identity, and raw notes: rejected because they are noisy, may expose
  personal data, and are not needed for a deterministic gate.
- Require Python on the clean machine: rejected because installing it would invalidate the most
  important distribution acceptance condition.

## Consequences

The final matrix still needs real machines or VMs and honest operator work; the tooling makes that
work portable, candidate-specific, privacy-minimized, and mechanically reviewable. A `not_run` or
failed observation remains visible and cannot be promoted to a pass. Signing changes the candidate
hash and therefore requires new bound evidence appropriate to the signed artifact before release.
