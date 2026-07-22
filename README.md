# TimbreScribe · 谱迹

> Turn sound into scores.

TimbreScribe 是一款本地优先、面向 Windows 的开源乐谱转录桌面工具。它的目标是把音频中的音符转换成可检查、可编辑的专业乐谱草稿，而不是承诺对任意混音生成完美成谱。

## 当前状态

项目处于 `v0.9.0` / Phase 8 Windows 发布候选加固阶段。固定的 PyInstaller onedir 同时生成 GUI 与隔离 Worker，打包经哈希验证的共享 FFmpeg、Verovio、Basic Pitch ONNX CPU 基线、许可证与逐文件 SHA-256 清单；Inno Setup 安装器默认按用户安装、支持 `.timbrescribe` 关联和保留数据的升级/卸载。助手仍默认关闭。Phase 5 的真实 MuScriptor Small 验收已在明确条款接受、经授权本地素材和精确模型哈希下通过；门控权重仍不会被下载或打入发布包。

`.timbrescribe` 项目采用带哈希清单的独立版本 ZIP 容器，保存使用原子替换，自动保存只写入独立恢复目录。加载器不解压到文件系统，会拒绝路径穿越、符号链接、重复/加密成员、异常压缩、过大内容、哈希不一致和派生乐谱不一致。MusicXML、MXL、乐谱 MIDI、SVG、PNG 与矢量 PDF 仍从同一不可变乐谱快照生成。

Mock 数据始终标记为“Mock/Test”，不能代表真实音频识别结果。Basic Pitch 是乐器无关的多音高转录基线，不做乐器分离，且对单一乐器录音效果最佳。Windows 候选包只包含审阅并验证过的 `nmp.onnx`，明确排除 TensorFlow/TFLite/CoreML。MuScriptor Small/Medium 的权重受门控且仅限非商业用途；应用不会自动下载、捆绑或替用户接受条款。置信度筛选只改变派生视图，不删除原始事件。速度、调号、和弦检测与助手提案都是需要人工确认的建议。当前范围止于私有未签名候选包，不申请证书、不创建公开标签或 GitHub Release；最终内部验收仍需无 Python Windows 10/11 与 Narrator/DPI 矩阵。

进度和已验证命令见 [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)。

## 开发环境

- Windows 10/11 x64
- Python 3.11 x64
- [uv](https://docs.astral.sh/uv/) 0.11.29 或兼容版本

```powershell
uv python pin 3.11
uv sync --group dev
./tools/setup_ffmpeg.ps1
uv run python -m timbrescribe
```

构建未签名 Windows 候选包（需已验证 FFmpeg 目录和 Basic Pitch 组）：

```powershell
uv sync --frozen --group dev --group basic-pitch
./packaging/scripts/build_onedir.ps1 -FfmpegDirectory C:\verified-ffmpeg\bin -Clean
./packaging/scripts/build_installer.ps1
$env:TIMBRESCRIBE_PACKAGED_APP = "$PWD\work\release\dist\TimbreScribe"
uv run pytest -m packaging --no-cov
```

第一次使用请先阅读 [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)；其中包含界面说明、Mock
练习、真实音频 Basic Pitch 转录、校对、项目保存和全部导出步骤。故障处理见
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)，发布门禁见
[`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)，不签名、不公开的当前范围见
[`docs/adr/0021-private-unsigned-candidate-scope.md`](docs/adr/0021-private-unsigned-candidate-scope.md)。

默认环境和 CI 保持模型无关。要启用 Basic Pitch ONNX CPU 基线：

```powershell
./tools/setup_basic_pitch.ps1
uv run python -m timbrescribe
```

FFmpeg 安装脚本下载固定的共享 LGPL 参考构建，并校验压缩包、`ffmpeg.exe` 和 `ffprobe.exe` 的 SHA-256。Basic Pitch 安装脚本验证引擎版本、ONNX 模型哈希和 CPU Runtime，并拒绝意外的 TensorFlow/CoreML/TFLite Runtime。首次同步依赖和首次获取组件需要网络；运行时不上传媒体。

要安装 MuScriptor 的可选 MIT 代码运行时（此步骤不下载权重、不代表接受模型条款）：

```powershell
./tools/setup_muscriptor.ps1
uv run python -m timbrescribe
```

随后只能在应用内醒目的“实验/非商业”面板审阅当前精确版本条款、显式记录接受、把令牌保存到操作系统凭据服务，并由模型管理器校验精确 revision、大小和 SHA-256。每次运行仍需单独确认源媒体权利。无 MuScriptor、无令牌、无权重时，其余功能保持完整可用。

助手不随应用捆绑模型，也不会自动下载 GGUF。若选择本地模式，请自行审阅模型许可证并在“Score assistant”页选择 `llama-server.exe` 和本地 `.gguf`；若选择云端模式，请填写无凭据的 HTTPS chat-completions 端点和模型 ID，并把 API Key 保存到操作系统凭据服务。发送前必须选择音符或明确小节范围、预览实际项目/request JSON，并逐次批准云端发送。完整边界见 [`docs/ASSISTANT_PRIVACY.md`](docs/ASSISTANT_PRIVACY.md)。

## 质量检查

```powershell
./tools/run_quality.ps1
```

等价的逐项命令：

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src/timbrescribe
uv run pytest -m "not model and not packaging"
```

## 架构边界

依赖方向为 `UI -> Application -> Domain`，基础设施适配器实现应用层端口。Mock、Basic Pitch 与 MuScriptor 推理都运行在独立 `QProcess` 中，通过版本化 JSON Lines 协议通信；模型库不会在 GUI 启动时导入。MuScriptor 的门控下载另有独立安装进程，令牌不进入协议、日志或项目。助手 Provider 只返回严格 schema 的命令信封；本地 llama-server 仅监听回环地址，云端调用在 GUI 线程外执行，API Key 只存在操作系统凭据库。FFmpeg 探测、解码和波形采样均在 GUI 线程之外执行。乐谱与编辑时间使用 `fractions.Fraction`；命令栈、版本令牌与不可变快照确保撤销和后台结果接纳可重现。固定版本的本地 Verovio 只接收生成并验证过的 MusicXML，预览不加载 CDN。

详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、[`docs/adr/`](docs/adr/) 和 ADR 0018。

## 隐私与版权

核心能力本地运行，默认不遥测、不上传文件。助手默认关闭；云端助手永远不接收音频、视频、项目归档、文件路径、凭据或与选区无关的数据。用户应确保拥有处理和导出源音乐所需的权利；本项目不是版权规避工具。测试仅使用合成或明确许可的素材。

## 许可证

项目代码以 [Apache License 2.0](LICENSE) 发布。第三方组件仍受各自许可证约束，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`docs/MODEL_LICENSES.md`](docs/MODEL_LICENSES.md)。
