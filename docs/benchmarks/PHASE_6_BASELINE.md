# Phase 6 long-score baseline

- Date: 2026-07-21
- Application: TimbreScribe 0.7.0 development branch
- Python: CPython 3.11.9
- Platform: Windows 10.0.19045, AMD64
- Processor: Intel64 Family 6 Model 158 Stepping 10, GenuineIntel
- Runs per scenario: 3; table values are medians
- Scenario: one piano part at 120 BPM, balanced quarter-grid quantization, one generated note every 0.125 seconds, MusicXML 4.0 rendering, and an 8 kHz deterministic pulse-preview WAV

| Notes | Measures | Notation | MusicXML | Score to MusicXML | Preview WAV | Peak working set |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 63 | 0.127 s | 0.074 s | 0.201 s | 0.299 s | 49.3 MiB |
| 10,000 | 625 | 1.305 s | 0.795 s | 2.100 s | 2.816 s | 114.2 MiB |

The pre-optimization 10,000-note exploratory run on the same machine took 22.240 seconds for notation and 7.867 seconds for preview synthesis. Measure construction previously scanned every note for every measure. It now indexes spans once, while score note order/measure count, MusicXML voice/staff lookup, harmony measure lookup, and preview pulse waveforms are cached or pre-indexed. An immediate three-run comparison against the selected 10,000-note baseline passed every metric with ratios from 1.0046 to 1.0117.

The documented regression threshold is 1.25x for every recorded timing metric. `benchmarks/score_pipeline.py --compare BASELINE.json` enforces that threshold only when note count, machine, and processor match. A hardware or scenario mismatch is reported as non-evaluated rather than treated as a guarantee across machines. Benchmark JSON remains an external run artifact; this milestone document records the selected baseline.
