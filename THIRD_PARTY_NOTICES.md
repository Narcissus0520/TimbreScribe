# Third-Party Notices

This document records direct dependencies used by the Phase 0 source distribution. A future packaged Windows release must expand this into an artifact-specific manifest with hashes, bundled files, source relationships, and all transitive notices.

| Component | Locked version | Source | License | Phase 0 distribution status |
|---|---:|---|---|---|
| PySide6 / Qt for Python | 6.11.1 | <https://pypi.org/project/PySide6/> | LGPL-3.0-only OR GPL-3.0-only OR commercial | Development dependency and dynamic runtime; packaging compliance remains pending |
| Shiboken6 | 6.11.1 | <https://pypi.org/project/shiboken6/> | LGPL-3.0-only OR GPL-3.0-only OR commercial | Installed with PySide6; packaging compliance remains pending |
| Pydantic | 2.13.4 | <https://pypi.org/project/pydantic/> | MIT | Python runtime dependency |
| Mido | 1.3.3 | <https://pypi.org/project/mido/> | MIT | Python runtime dependency for Standard MIDI File export |

Development-only tools, their transitive packages, and exact hashes are pinned in `uv.lock`. They are not automatically redistributed with the end-user application.

No FFmpeg binary, Verovio asset, model weight, SoundFont, sample song, or other downloadable runtime is included in Phase 0.

This file preserves engineering evidence and is not legal advice.
