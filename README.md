# TimbreScribe · 谱迹

> Turn sound into scores.

TimbreScribe 是一款本地优先、面向 Windows 的开源乐谱转录桌面工具。它的目标是把音频中的音符转换成可检查、可编辑的专业乐谱草稿，而不是承诺对任意混音生成完美成谱。

## 当前状态

项目处于 `v0.1.0` / Phase 0 仓库启动阶段。一个完全离线、无需真实 AI 模型的 Mock 垂直切片已经实现并通过本地质量门禁：独立 Worker 产生确定性音符，应用将其转换为内部乐谱，显示预览，并原子导出 MusicXML 与 MIDI。GitHub CI 与合入状态以项目状态文档为准。

Mock 数据始终标记为“Mock/Test”，不能代表真实音频识别结果。真实媒体导入、Basic Pitch、Verovio 本地渲染、编辑器与项目持久化属于后续有序里程碑。

进度和已验证命令见 [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)。

## 开发环境

- Windows 10/11 x64
- Python 3.11 x64
- [uv](https://docs.astral.sh/uv/) 0.11.29 或兼容版本

```powershell
uv python pin 3.11
uv sync --group dev
uv run python -m timbrescribe
```

应用的核心 Mock 流程无需网络、模型、FFmpeg 或 MuseScore。首次同步 Python 依赖需要访问包索引。

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

依赖方向为 `UI -> Application -> Domain`，基础设施适配器实现应用层端口。Mock 推理运行在独立 `QProcess` 中，通过版本化 JSON Lines 协议通信；标准输出只承载协议，诊断写入标准错误。乐谱时间使用 `fractions.Fraction`，MusicXML/MIDI 导出使用一致的内部乐谱快照。

详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 和 [`docs/adr/`](docs/adr/)。

## 隐私与版权

核心能力本地运行，默认不遥测、不上传文件。用户应确保拥有处理和导出源音乐所需的权利；本项目不是版权规避工具。测试仅使用合成或明确许可的素材。

## 许可证

项目代码以 [Apache License 2.0](LICENSE) 发布。第三方组件仍受各自许可证约束，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和 [`docs/MODEL_LICENSES.md`](docs/MODEL_LICENSES.md)。
