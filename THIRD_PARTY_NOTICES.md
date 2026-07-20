# Third-Party Notices

This document records direct dependencies, the Phase 1 FFmpeg reference component, and the optional Phase 2 model environment. A future packaged Windows release must expand this into an artifact-specific manifest with bundled files, source relationships, and all transitive notices.

| Component | Locked version | Source | License | Current distribution status |
|---|---:|---|---|---|
| PySide6 / Qt for Python | 6.11.1 | <https://pypi.org/project/PySide6/> | LGPL-3.0-only OR GPL-3.0-only OR commercial | Development dependency and dynamic runtime; packaging compliance remains pending |
| Shiboken6 | 6.11.1 | <https://pypi.org/project/shiboken6/> | LGPL-3.0-only OR GPL-3.0-only OR commercial | Installed with PySide6; packaging compliance remains pending |
| Pydantic | 2.13.4 | <https://pypi.org/project/pydantic/> | MIT | Python runtime dependency |
| Mido | 1.3.3 | <https://pypi.org/project/mido/> | MIT | Python runtime dependency for Standard MIDI File export |
| FFmpeg shared reference | n8.1.2-21-gce3c09c101-20260630 | <https://github.com/BtbN/FFmpeg-Builds> / <https://github.com/FFmpeg/FFmpeg/commit/ce3c09c101> | LGPL-2.1-or-later as declared by the selected build | Downloaded and hash-verified for development/CI; not committed or redistributed in the source tree |
| Spotify Basic Pitch | 0.4.0 | <https://github.com/spotify/basic-pitch> | Apache-2.0 | Optional developer model environment; upstream wheel and ONNX model are not committed or included in the TimbreScribe wheel |
| ONNX Runtime | 1.27.0 | <https://github.com/microsoft/onnxruntime> | MIT | Optional CPU inference runtime installed with the Basic Pitch developer group |

Development-only tools, their transitive packages, and exact hashes are pinned in `uv.lock`. They are not automatically redistributed with the end-user application.

The FFmpeg archive SHA-256, executable hashes, exact configuration, source links, and release-compliance caveat are recorded in `packaging/third_party/ffmpeg/`. The Basic Pitch wheel and model hashes and redistribution caveat are recorded in `docs/MODEL_LICENSES.md` and the packaged runtime manifest. No FFmpeg binary, Verovio asset, model weight, SoundFont, sample song, or other downloadable runtime is committed to the repository.

This file preserves engineering evidence and is not legal advice.
