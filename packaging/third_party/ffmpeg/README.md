# FFmpeg reference component

Phase 1 does not commit or redistribute FFmpeg binaries. Development and CI use one exact replaceable shared build, downloaded by `tools/setup_ffmpeg.ps1` and verified before execution.

| Field | Recorded value |
|---|---|
| Package | `BtbN.FFmpeg.LGPL.Shared.8.1` |
| Package version | `8.1.2-20260630` |
| FFmpeg version | `n8.1.2-21-gce3c09c101-20260630` |
| Upstream archive | `ffmpeg-n8.1.2-21-gce3c09c101-win64-lgpl-shared-8.1.zip` |
| Archive SHA-256 | `27bcaf58b5140171dfe838a0b365d12c60607d71fc168424456410bad6a834da` |
| `ffmpeg.exe` SHA-256 | `abe4f6dc7ca6d807c9492e56f96db9030d7c5faba942254aa00d4474042048d4` |
| `ffprobe.exe` SHA-256 | `f1b2041be46d1d2e1e2f77f950de6fe624cdf65b692c04f880b6ce81e99e03a1` |
| Declared build license | LGPL-2.1-or-later |
| Binary source | <https://github.com/BtbN/FFmpeg-Builds> |
| Corresponding FFmpeg source | <https://github.com/FFmpeg/FFmpeg/commit/ce3c09c101> |
| FFmpeg legal guidance | <https://ffmpeg.org/legal.html> |

The recorded configuration is in `CONFIGURATION.txt`. It uses shared libraries, disables static binaries, x264, x265, Xvid, and nonfree FDK AAC, and does not enable `nonfree`. Exact binary redistribution and corresponding-source obligations remain a release-hardening gate; this record is engineering evidence, not legal advice.
