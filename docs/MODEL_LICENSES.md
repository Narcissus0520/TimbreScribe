# Model Licenses

## Spotify Basic Pitch ICASSP 2022 ONNX

| Field | Recorded value |
|---|---|
| Provider | Spotify |
| Engine package | `basic-pitch==0.4.0` |
| Engine wheel SHA-256 | `738adb503aae7fdfc7d1e1511aa0ce35052315f260a19531ef4c356708425db0` |
| Model ID | `spotify/basic-pitch-icassp-2022-onnx` |
| Model revision | `basic-pitch-0.4.0:nmp.onnx` |
| Model SHA-256 | `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec` |
| Code license | Apache-2.0 (`basic-pitch` repository and wheel license) |
| Weight license | No separate weight license is present in the verified 0.4.0 wheel; the bundled ONNX file is treated under the repository/wheel Apache-2.0 notice pending release review |
| Commercial use | Apache-2.0 permits commercial use, subject to its terms and the future packaged artifact review |
| Gating / acceptance | None observed for the public PyPI wheel |
| Current distribution | Downloaded only by the optional developer group; neither wheel nor model is committed or included in the TimbreScribe wheel |

The application verifies the exact model hash before enabling the engine. The optional `uv` group excludes TensorFlow, CoreML, and TFLite dependencies from Basic Pitch's upstream Python 3.11 metadata and installs ONNX Runtime CPU only. Because `resampy` 0.4.2 imports the removed `pkg_resources.resource_filename` API, the isolated model process supplies only that one operation using `importlib`; it does not install Setuptools for runtime compatibility. This is a repository-local development resolution, not a public pip extra; a future installer must reproduce and audit the resolved artifact explicitly.

Future model entries must record the same fields. MuScriptor weights must never be committed or bundled.
