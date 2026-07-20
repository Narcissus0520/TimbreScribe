# ADR 0013: Pinned Verovio toolkit and shared visual-export pipeline

- Status: Accepted
- Date: 2026-07-21

## Context

ADR 0005 selected local Verovio rendering but intentionally deferred the concrete integration and compliance evidence. Phase 3 needs deterministic multi-page rendering, offline preview, SVG/PNG/PDF export that visually agrees with preview, and a browser boundary that cannot become arbitrary native or network access. The project also needs a Python 3.11 Windows artifact that can be locked and tested without a runtime CDN.

## Decision

Pin `verovio==6.2.1` and call its local Python toolkit directly. MusicXML 4.0 remains the canonical renderer input. Reject output whose XML contains external declarations, scripts, foreign objects, event handlers, or external links. Display sanitized SVG in `QWebEngineView` with JavaScript, file access, remote access, plugins, and full-screen disabled; expose no web channel or native bridge. CI's offscreen platform may use a non-linking static HTML widget because Chromium child processes make pytest shutdown nondeterministic there.

Use the same sanitized Verovio SVG products for preview and export. Continuous SVG is written directly; QtSvg performs explicit-DPI PNG rasterization; QtSvg paints each page directly into `QPdfWriter` for vector PDF. All outputs use sibling temporary files and atomic replacement.

Record the official source, LGPL-3.0-or-later license, exact locked version, and CPython 3.11 Windows wheel hash in third-party notices. Packaged releases must preserve license/source/replacement obligations; this milestone does not claim installer compliance.

## Alternatives

- CDN or remote WebAssembly/JavaScript Verovio: rejected because it violates offline, privacy, integrity, and reproducibility requirements.
- Render preview with Verovio but export through another engraver: rejected because visual divergence would make preview unreliable.
- Rasterize PDF pages: rejected because professional notation output must remain vector.
- Expose a `QWebChannel` bridge: rejected because navigation and editing need no arbitrary browser-to-native capability in this milestone.

## Consequences

Preview and visual exports have one pinned engraving source and can be tested with real generated MusicXML. The native wheel becomes a runtime and future packaging/compliance responsibility. MuseScore remains an external optional interoperability check, not an embedded renderer or hidden dependency.
