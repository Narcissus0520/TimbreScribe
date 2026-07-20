# TimbreScribe · 谱迹

> Turn sound into scores.

TimbreScribe 是一款本地优先、面向 Windows 的开源乐谱转录桌面工具。它的目标是把音频中的音符转换成可检查、可编辑的专业乐谱草稿，而不是承诺对任意混音生成完美成谱。

## 当前状态

项目处于 `v0.5.0` / Phase 4 编辑工作区与项目持久化阶段。应用可异步导入经过验证的 WAV、MP3 和 MP4，运行独立 Mock 或可选 Basic Pitch Worker，审阅量化与乐器设置，并生成 Verovio 专业预览。可编辑钢琴卷帘支持稳定 ID 多选、添加、删除、移动、缩放、力度、声部与谱表修改；所有操作都通过命令栈可靠撤销/重做。原始转录、物理时间编辑事件和派生乐谱保持分离。

`.timbrescribe` 项目采用带哈希清单的独立版本 ZIP 容器，保存使用原子替换，自动保存只写入独立恢复目录。加载器不解压到文件系统，会拒绝路径穿越、符号链接、重复/加密成员、异常压缩、过大内容、哈希不一致和派生乐谱不一致。MusicXML、MXL、乐谱 MIDI、SVG、PNG 与矢量 PDF 仍从同一不可变乐谱快照生成。

Mock 数据始终标记为“Mock/Test”，不能代表真实音频识别结果。Basic Pitch 是乐器无关的多音高转录基线，不做乐器分离，且对单一乐器录音效果最佳。置信度筛选只改变派生视图，不删除原始事件。速度和调号检测是需要人工确认的建议。多声部模型、打击乐整理、合成器完善、可选助手与发布打包仍属于后续有序里程碑。

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

依赖方向为 `UI -> Application -> Domain`，基础设施适配器实现应用层端口。Mock 与 Basic Pitch 推理都运行在独立 `QProcess` 中，通过版本化 JSON Lines 协议通信；Basic Pitch Worker 跨任务复用一个 ONNX 模型实例。FFmpeg 探测、解码和波形采样均在 GUI 线程之外执行。乐谱与编辑时间使用 `fractions.Fraction`；命令栈、版本令牌与不可变快照确保撤销和后台结果接纳可重现。固定版本的本地 Verovio 只接收生成并验证过的 MusicXML，预览不加载 CDN。

详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 和 [`docs/adr/`](docs/adr/)。

## 隐私与版权

核心能力本地运行，默认不遥测、不上传文件。用户应确保拥有处理和导出源音乐所需的权利；本项目不是版权规避工具。测试仅使用合成或明确许可的素材。

## 许可证

项目代码以 [Apache License 2.0](LICENSE) 发布。第三方组件仍受各自许可证约束，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`docs/MODEL_LICENSES.md`](docs/MODEL_LICENSES.md)。
