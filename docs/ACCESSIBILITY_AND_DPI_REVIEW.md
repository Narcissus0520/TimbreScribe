# Accessibility and High-DPI Review

## Implemented review evidence

| Area | Evidence | Result |
|---|---|---|
| Windows DPI | Qt `PassThrough` scale rounding policy is set before `QApplication`; layouts avoid fixed main-window geometry | Implemented and offscreen-smoke covered |
| Themes | Dark and light styles use explicit foreground/background/control states; light selection uses dark blue; disabled states remain distinct | Implemented; both paths have GUI coverage |
| Keyboard focus | Buttons, tool buttons, combos, spin boxes, text inputs and tabs have a visible 2 px blue focus border; native menus/toolbars/tabs retain keyboard navigation | Implemented |
| Accessible names | Main workspaces, score/waveform/piano-roll/Verovio canvases, generated XML, Mock controls, diagnostics, progress, and About license panes have semantic names | Automated construction coverage |
| Text scaling/layout | Qt layouts and scrollable/dockable workspaces are used; no bitmap-rendered UI text is required | Code review passed |
| Dock reachability | Initial left/right/bottom proportions prevent title-bar-only collapse; MuScriptor and notation forms scroll; named `View` actions activate every dock without relying on truncated tab labels | GUI regression test and live-window review passed |
| Non-color state | Worker state, diagnostics, confidence, destructive assistant diff, unavailable engines, and Mock/Test identity use text in addition to color | Code/GUI review passed |
| Light-theme path | View menu toggle is persisted through `QSettings` and can be reversed | GUI test passed |

Keyboard-only manual RC steps: launch, traverse menus/toolbars/tabs with Alt/Tab/Shift+Tab, open a
project, run/cancel Mock, edit/undo, export, open About, toggle light theme, and dismiss every dialog
without a pointer. Test Windows scale factors 100%, 150%, 200% on one 1920×1080 and one high-DPI
display, checking clipped labels, dock reachability, modal buttons, score zoom, and focus visibility.

Screen-reader RC steps: inspect the main window and About dialog with Windows Narrator, confirm the
named custom canvases/diagnostics/progress are announced, and record any unlabeled dynamic control as
a release defect. Automated tests cannot establish speech order or musical-canvas usability; final
v1 requires this manual Narrator/display matrix and closure of all P0/P1 findings.
