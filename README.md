# TimbreScribe · 谱迹

> Turn sound into scores.

TimbreScribe 是一款本地优先、面向 Windows 的开源乐谱转录桌面工具。它的目标是把音频中的音符转换成可检查、可编辑的专业乐谱草稿，而不是承诺对任意混音生成完美成谱。

## 当前状态

项目处于 `v0.4.0` / Phase 3 乐谱整理与专业导出阶段。应用可异步导入经过验证的 WAV、MP3 和 MP4，选择音频流和分析范围，播放源媒体，并解码到内容寻址缓存。安装可选模型环境后，可在独立持久 Worker 中运行经过哈希验证的 Basic Pitch 0.4.0 ONNX CPU 模型。用户可审阅速度、调号、拍号、乐器、移调视图与量化设置，再把不可变原始事件转换为精确的小节、休止符、声部和跨小节连音。MusicXML、MXL、乐谱 MIDI、SVG、PNG 与矢量 PDF 均从同一内部乐谱快照原子生成，本地 Verovio 6.2.1 提供多页专业预览。

Mock 数据始终标记为“Mock/Test”，不能代表真实音频识别结果。Basic Pitch 是乐器无关的多音高转录基线，不做乐器分离，且对单一乐器录音效果最佳。置信度筛选只改变派生视图，不删除原始事件。速度和调号检测是需要人工确认的建议。直接音符编辑、撤销/重做与项目持久化属于后续有序里程碑。

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

默认环境和 CI 保持模型无关。要启用 Basic Pitch ONNX CPU 基线：

```powershell
./tools/setup_basic_pitch.ps1
uv run python -m timbrescribe
```

FFmpeg 安装脚本下载固定的共享 LGPL 参考构建，并校验压缩包、`ffmpeg.exe` 和 `ffprobe.exe` 的 SHA-256。Basic Pitch 安装脚本验证引擎版本、ONNX 模型哈希和 CPU Runtime，并拒绝意外的 TensorFlow/CoreML/TFLite Runtime。首次同步依赖和首次获取组件需要网络；运行时不上传媒体。

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

依赖方向为 `UI -> Application -> Domain`，基础设施适配器实现应用层端口。Mock 与 Basic Pitch 推理都运行在独立 `QProcess` 中，通过版本化 JSON Lines 协议通信；Basic Pitch Worker 跨任务复用一个 ONNX 模型实例。FFmpeg 探测、解码和波形采样均在 GUI 线程之外执行。乐谱时间使用 `fractions.Fraction`；量化、分声部、移调、小节闭合与连音均在纯领域流水线中完成。固定版本的本地 Verovio 只接收生成并验证过的 MusicXML，预览不加载 CDN。

详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 和 [`docs/adr/`](docs/adr/)。

## 隐私与版权

核心能力本地运行，默认不遥测、不上传文件。用户应确保拥有处理和导出源音乐所需的权利；本项目不是版权规避工具。测试仅使用合成或明确许可的素材。

## 许可证

项目代码以 [Apache License 2.0](LICENSE) 发布。第三方组件仍受各自许可证约束，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`docs/MODEL_LICENSES.md`](docs/MODEL_LICENSES.md)。
