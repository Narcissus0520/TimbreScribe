"""Deterministic release-smoke inspection for high-DPI window layouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDockWidget, QScrollArea, QTabBar, QWidget

from timbrescribe.ui.main_window import MainWindow

_DEFAULT_PHYSICAL_SIZE = (1920, 1080)
_EXPECTED_WORKSPACE_LABELS = {"媒体", "Mock", "Basic", "MuScriptor", "乐谱"}


@dataclass(frozen=True)
class _WorkspaceMetrics:
    labels: tuple[str, ...]
    hints_width: int
    bar_width: int
    tabs_fit: bool
    scrollable: bool

    @property
    def usable(self) -> bool:
        return self.tabs_fit and set(self.labels) == _EXPECTED_WORKSPACE_LABELS and self.scrollable


@dataclass(frozen=True)
class _DockMetrics:
    left_width: int
    right_width: int
    diagnostics_height: int
    central_width: int
    central_height: int

    @property
    def usable(self) -> bool:
        return (
            self.left_width >= 400
            and self.right_width >= 180
            and self.diagnostics_height >= 96
            and self.central_width > 0
            and self.central_height > 0
        )


def parse_smoke_arguments(
    arguments: list[str],
) -> tuple[Path | None, tuple[int, int]] | None:
    """Parse the deliberately small smoke-test CLI without accepting unknown flags."""

    if len(arguments) % 2:
        return None
    destination: Path | None = None
    physical_size = _DEFAULT_PHYSICAL_SIZE
    seen: set[str] = set()
    for index in range(0, len(arguments), 2):
        option, value = arguments[index : index + 2]
        if option in seen or option not in {"--report", "--physical-size"}:
            return None
        seen.add(option)
        if option == "--report":
            if not value:
                return None
            destination = Path(value)
            continue
        parsed_size = _parse_physical_size(value)
        if parsed_size is None:
            return None
        physical_size = parsed_size
    return destination, physical_size


def collect_smoke_layout(
    application: QApplication,
    window: MainWindow,
    physical_size: tuple[int, int],
) -> dict[str, object]:
    """Resize for one physical viewport and return machine-readable layout evidence."""

    scale_factor, logical_size = _resize_for_physical_viewport(
        application,
        window,
        physical_size,
    )
    workspace = _workspace_metrics(window)
    docks = _dock_metrics(window)
    accessible_names_present = _critical_accessible_names_present(window)
    fits_viewport = window.width() <= logical_size[0] and window.height() <= logical_size[1]
    usable = fits_viewport and workspace.usable and docks.usable and accessible_names_present
    return {
        "scale_factor": scale_factor,
        "physical_viewport": {"width": physical_size[0], "height": physical_size[1]},
        "logical_viewport": {"width": logical_size[0], "height": logical_size[1]},
        "window": _window_metrics(window),
        "fits_viewport": fits_viewport,
        "dock_geometry_usable": docks.usable,
        "dock_geometry": {
            "left_width": docks.left_width,
            "right_width": docks.right_width,
            "diagnostics_height": docks.diagnostics_height,
            "central_width": docks.central_width,
            "central_height": docks.central_height,
        },
        "workspace_tab_labels": list(workspace.labels),
        "workspace_tab_hints_width": workspace.hints_width,
        "workspace_tab_bar_width": workspace.bar_width,
        "workspace_tabs_fit": workspace.tabs_fit,
        "scrollable_workspaces": workspace.scrollable,
        "accessible_names_present": accessible_names_present,
        "usable": usable,
    }


def _parse_physical_size(value: str) -> tuple[int, int] | None:
    dimensions = value.lower().split("x")
    if len(dimensions) != 2:
        return None
    try:
        width, height = (int(dimension) for dimension in dimensions)
    except ValueError:
        return None
    return (width, height) if 640 <= width <= 16_384 and 480 <= height <= 16_384 else None


def _resize_for_physical_viewport(
    application: QApplication,
    window: MainWindow,
    physical_size: tuple[int, int],
) -> tuple[float, tuple[int, int]]:
    window.show()
    application.processEvents()
    scale_factor = max(1.0, float(window.devicePixelRatioF()))
    logical_size = (
        round(physical_size[0] / scale_factor),
        round(physical_size[1] / scale_factor),
    )
    window.resize(*logical_size)
    application.processEvents()
    return scale_factor, logical_size


def _workspace_metrics(window: MainWindow) -> _WorkspaceMetrics:
    tab_bar = window.findChild(QTabBar, "workspaceDockTabBar")
    muscriptor_scroll = window.muscriptor_workspace.findChild(
        QScrollArea,
        "muscriptorScrollArea",
    )
    notation_scroll = window.notation_workspace.findChild(
        QScrollArea,
        "notationScrollArea",
    )
    labels = (
        tuple(tab_bar.tabText(index) for index in range(tab_bar.count()))
        if tab_bar is not None
        else ()
    )
    hints_width = (
        sum(tab_bar.tabSizeHint(index).width() for index in range(tab_bar.count()))
        if tab_bar is not None
        else 0
    )
    bar_width = tab_bar.width() if tab_bar is not None else 0
    return _WorkspaceMetrics(
        labels=labels,
        hints_width=hints_width,
        bar_width=bar_width,
        tabs_fit=tab_bar is not None and hints_width <= bar_width,
        scrollable=bool(
            muscriptor_scroll is not None
            and muscriptor_scroll.widgetResizable()
            and notation_scroll is not None
            and notation_scroll.widgetResizable()
        ),
    )


def _dock_metrics(window: MainWindow) -> _DockMetrics:
    left = window.findChild(QDockWidget, "sourceMediaDock")
    right = window.findChild(QDockWidget, "scoreInspectorDock")
    diagnostics = window.findChild(QDockWidget, "diagnosticsDock")
    central = window.centralWidget()
    return _DockMetrics(
        left_width=left.width() if left is not None else 0,
        right_width=right.width() if right is not None else 0,
        diagnostics_height=diagnostics.height() if diagnostics is not None else 0,
        central_width=central.width() if central is not None else 0,
        central_height=central.height() if central is not None else 0,
    )


def _critical_accessible_names_present(window: MainWindow) -> bool:
    controls: tuple[QWidget | None, ...] = (
        window.tabs,
        window.score_preview,
        window.verovio_view,
        window.musicxml_preview,
        window.waveform_view,
        window.piano_roll_view,
        window.editing_workspace,
        window.assistant_workspace,
        window.diagnostics,
        window.progress_bar,
        window.findChild(QTabBar, "workspaceDockTabBar"),
    )
    return all(
        control is not None and bool(control.accessibleName().strip()) for control in controls
    )


def _window_metrics(window: MainWindow) -> dict[str, int]:
    return {
        "width": window.width(),
        "height": window.height(),
        "minimum_width": window.minimumWidth(),
        "minimum_height": window.minimumHeight(),
    }
