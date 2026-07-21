# Third-Party Notices

This source-tree overview identifies the direct components intentionally distributed by the
TimbreScribe Windows onedir/installer. Every built artifact also contains
`licenses/THIRD_PARTY_INVENTORY.json` plus the license/notice files discovered from each resolved
runtime distribution. `manifests/release-manifest.json` binds those notices and every other file to
its exact size and SHA-256. Build and test tools are locked in `uv.lock` but are not redistributed.

| Component | Locked version | Source | License | Windows artifact decision |
|---|---:|---|---|---|
| PySide6 / Qt for Python / Shiboken6 | 6.11.1 | <https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.1> | LGPL-3.0-only OR GPL-3.0-only OR commercial | Dynamic Qt/PySide DLLs are bundled under the LGPL path; license text, exact source links, relinking information, and per-wheel notices are included |
| Pydantic / pydantic-core | 2.13.4 / 2.41.5 | <https://github.com/pydantic/pydantic> | MIT | Bundled Python runtime; artifact inventory records transitive notices |
| Mido | 1.3.3 | <https://github.com/mido/mido> | MIT | Bundled for Standard MIDI File export |
| Verovio | 6.2.1 | <https://github.com/rism-digital/verovio> | LGPL-3.0-or-later | Bundled local CPython toolkit; `COPYING` and `COPYING.LESSER` are staged |
| FFmpeg shared build | n8.1.2-21-gce3c09c101-20260630 | <https://github.com/BtbN/FFmpeg-Builds> / <https://github.com/FFmpeg/FFmpeg/commit/ce3c09c101> | LGPL-2.1-or-later for the selected configuration | Hash-verified shared executables/DLLs are bundled in replaceable `ffmpeg/`; license, configuration, source relationship, archive and executable hashes are included |
| Spotify Basic Pitch | 0.4.0 | <https://github.com/spotify/basic-pitch> | Apache-2.0 | The release environment bundles only the verified `nmp.onnx` model; TensorFlow, CoreML and TFLite models/runtimes are excluded |
| ONNX Runtime CPU | 1.27.0 | <https://github.com/microsoft/onnxruntime> | MIT | Bundled for Basic Pitch CPU inference; upstream `LICENSE` and `ThirdPartyNotices.txt` are staged |
| NumPy / SciPy / scikit-learn / librosa and inference dependencies | versions locked in `uv.lock` and artifact inventory | project URLs in artifact inventory | respective permissive/open-source terms | Only resolved Windows runtime files are bundled; distribution license classifiers/texts and versions are staged automatically |
| keyring and Windows credential backend | 25.7.0 plus locked transitives | <https://github.com/jaraco/keyring> | MIT | Bundled to store optional provider/model credentials in the OS credential service; no credentials are distributed |
| MuScriptor engine | 0.2.1 | <https://github.com/muscriptor/muscriptor> | MIT | Not bundled in the v0.9 Windows artifact; optional source/developer group only |
| MuScriptor Small/Medium weights | immutable revisions in `docs/MODEL_LICENSES.md` | <https://huggingface.co/MuScriptor> | CC BY-NC 4.0 plus provider conditions | Never bundled; locally gated, non-commercial, exact-revision download only after user acceptance |
| User-supplied assistant runtime/model | user-selected | user-selected | user must review | No llama.cpp executable, GGUF, cloud key, or permanent model is bundled |

The Basic Pitch engine wheel SHA-256 is
`738adb503aae7fdfc7d1e1511aa0ce35052315f260a19531ef4c356708425db0`; the
single distributed ONNX file SHA-256 is
`2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`.
The Verovio CPython 3.11 Windows wheel SHA-256 is
`d39542e5d8120f73e396dcdcb1a09a4085bd7085fbcd1a50258634d47bb78187`.
FFmpeg archive/binary hashes and its complete selected configuration are under
`packaging/third_party/ffmpeg/`.

The application About dialog exposes the project license/notice, this overview, the generated
artifact inventory, model terms, and assistant privacy boundary. Individual dependency texts stay
beside it under `licenses/python/`. No FFmpeg binary or model weight is committed to the source
repository; approved redistributable assets are staged only by the verified release build.

This file preserves engineering evidence and is not legal advice.
