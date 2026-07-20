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

## MuScriptor Small / Medium

| Field | Recorded value |
|---|---|
| Provider | MuScriptor authors / Hugging Face organization `MuScriptor` |
| Engine package | `muscriptor==0.2.1` |
| Engine source revision | tag/commit `964e2350d5677eb3c3ca4d29e0e03286671e910a` |
| Engine wheel SHA-256 | `eeaf6dc7b3c7d28480ef20f4c494a727c890865d36f261d76dd885ea1172c315` |
| Code license | MIT |
| Small model | `MuScriptor/muscriptor-small` revision `8c127f603b807520fa465c838e9bfee8a91ada4e` |
| Small safetensors | 411,888,600 bytes; SHA-256 `bbd482c786b895cf7d8f44185073d951adae2ebb8a66f82ca84cd1f84569549c` |
| Medium model | `MuScriptor/muscriptor-medium` revision `f32236969308476e01fd3aae67357de5feb05a2d` |
| Medium safetensors | 1,228,144,472 bytes; SHA-256 `ac80adbdf85d87231735fd948af7013441c0afced316c4e9067fd5d8a7fb97ec` |
| Weight license | CC BY-NC 4.0 plus the provider's gated access conditions for the exact revision |
| Commercial use | Not permitted by the recorded weight terms; the feature is visibly marked non-commercial |
| Gating / acceptance | Explicit per-revision in-app acceptance before network access; per-run source-media-rights confirmation; token stored only through the OS credential service |
| Current distribution | Engine code is an optional development group. Weights are not committed, bundled, cached in release artifacts, or downloaded by default/CI |

The Small and Medium records are independent. A terms/revision change invalidates the corresponding local acceptance and hash verification. TimbreScribe's installer requests only the immutable `model.safetensors` and `config.json`, verifies size/hash/configuration, and promotes them only into its managed application-data directory. The inference worker accepts only that verified local safetensors path and does not enable remote code. Medium stays disabled until the exact Small installation verifies.

The provider conditions require the operator to have the necessary rights or permission for source music and output use. TimbreScribe records a non-secret terms version and per-run rights confirmation for provenance, but this is engineering evidence rather than legal advice. No project contributor or automated test accepts the provider's terms on a user's behalf.
