"""Visible experimental/non-commercial MuScriptor model and run controls."""

from __future__ import annotations

from typing import Literal, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.engines import EngineDescriptor, ModelManifest
from timbrescribe.domain.notation import MUSCRIPTOR_INSTRUMENT_LABELS
from timbrescribe.infrastructure.muscriptor import MuscriptorModelStatus, ResourcePreflight


class MuscriptorWorkspace(QWidget):
    variant_changed = Signal()
    device_changed = Signal()
    accept_terms_requested = Signal()
    save_token_requested = Signal(str)
    delete_token_requested = Signal()
    install_requested = Signal()
    delete_model_requested = Signal()
    run_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, descriptor: EngineDescriptor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.experimental_notice = QLabel(
            self.tr(
                "EXPERIMENTAL / NON-COMMERCIAL: MuScriptor results require review. "
                "Model weights are gated and are never bundled with TimbreScribe."
            ),
            self,
        )
        self.experimental_notice.setWordWrap(True)
        self.experimental_notice.setStyleSheet(
            "QLabel { background: #5a3412; color: #ffe4b5; padding: 8px; font-weight: bold; }"
        )
        self.terms_link = QLabel(self)
        self.terms_link.setWordWrap(True)
        self.terms_link.setOpenExternalLinks(True)
        self.status_label = QLabel(self.tr("Checking optional runtime and models…"), self)
        self.status_label.setWordWrap(True)
        self.resource_label = QLabel(self)
        self.resource_label.setWordWrap(True)

        model_box = QGroupBox(self.tr("Gated model manager"), self)
        model_form = QFormLayout(model_box)
        self.variant = QComboBox(model_box)
        self.variant.addItem(self.tr("Small — stable first choice"), "small")
        self.variant.addItem(self.tr("Medium — after Small is verified"), "medium")
        self.device = QComboBox(model_box)
        self.device.addItem(self.tr("CPU fallback"), "cpu")
        self.device.addItem(self.tr("NVIDIA CUDA"), "cuda")
        self.terms_reviewed = QCheckBox(
            self.tr("I reviewed the current CC BY-NC 4.0 and provider conditions"), model_box
        )
        self.accept_terms_button = QPushButton(self.tr("Record explicit acceptance"), model_box)
        self.accept_terms_button.setEnabled(False)
        self.acceptance_label = QLabel(self.tr("Terms not accepted"), model_box)
        self.token = QLineEdit(model_box)
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText(self.tr("Hugging Face gated-model token"))
        self.save_token_button = QPushButton(self.tr("Save token in system credentials"), model_box)
        self.delete_token_button = QPushButton(self.tr("Delete stored token"), model_box)
        token_buttons = QWidget(model_box)
        token_layout = QHBoxLayout(token_buttons)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.addWidget(self.save_token_button)
        token_layout.addWidget(self.delete_token_button)
        self.token_status = QLabel(self.tr("No stored token"), model_box)
        self.install_button = QPushButton(self.tr("Install selected verified model"), model_box)
        self.delete_model_button = QPushButton(self.tr("Delete selected managed model"), model_box)
        model_form.addRow(self.tr("Variant"), self.variant)
        model_form.addRow(self.tr("Device"), self.device)
        model_form.addRow(self.terms_reviewed)
        model_form.addRow(self.accept_terms_button)
        model_form.addRow(self.tr("Acceptance"), self.acceptance_label)
        model_form.addRow(self.tr("Token"), self.token)
        model_form.addRow(token_buttons)
        model_form.addRow(self.token_status)
        model_form.addRow(self.install_button)
        model_form.addRow(self.delete_model_button)

        conditioning_box = QGroupBox(self.tr("Instrument conditioning (capability-based)"), self)
        conditioning_layout = QVBoxLayout(conditioning_box)
        conditioning_help = QLabel(
            self.tr(
                "Optional: select only instruments you have reason to expect. "
                "This guides the model; it does not guarantee identification."
            ),
            conditioning_box,
        )
        conditioning_help.setWordWrap(True)
        self.instruments = QListWidget(conditioning_box)
        self.instruments.setMaximumHeight(180)
        for label in MUSCRIPTOR_INSTRUMENT_LABELS:
            item = QListWidgetItem(label.replace("_", " ").title(), self.instruments)
            item.setData(Qt.ItemDataRole.UserRole, label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
        self.instruments.setEnabled(descriptor.capabilities.supports_instrument_conditioning)
        conditioning_layout.addWidget(conditioning_help)
        conditioning_layout.addWidget(self.instruments)

        self.rights_confirmed = QCheckBox(
            self.tr(
                "For this run, I confirm I have all necessary rights to the source music and output"
            ),
            self,
        )
        self.run_button = QPushButton(self.tr("Run MuScriptor (experimental)"), self)
        self.cancel_button = QPushButton(self.tr("Cancel and preserve current project"), self)
        self.cancel_button.setEnabled(False)

        body = QWidget(self)
        body.setObjectName("muscriptorScrollBody")
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(self.experimental_notice)
        body_layout.addWidget(self.terms_link)
        body_layout.addWidget(self.status_label)
        body_layout.addWidget(self.resource_label)
        body_layout.addWidget(model_box)
        body_layout.addWidget(conditioning_box)
        body_layout.addWidget(self.rights_confirmed)
        body_layout.addWidget(self.run_button)
        body_layout.addWidget(self.cancel_button)
        body_layout.addStretch(1)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("muscriptorScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(body)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)
        self._connect_signals()

    @property
    def selected_variant(self) -> Literal["small", "medium"]:
        return cast(Literal["small", "medium"], self.variant.currentData())

    @property
    def selected_device(self) -> Literal["cpu", "cuda"]:
        return cast(Literal["cpu", "cuda"], self.device.currentData())

    @property
    def selected_instruments(self) -> tuple[str, ...]:
        return tuple(
            str(self.instruments.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.instruments.count())
            if self.instruments.item(index).checkState() == Qt.CheckState.Checked
        )

    def set_state(
        self,
        *,
        manifest: ModelManifest,
        status: MuscriptorModelStatus,
        accepted: bool,
        token_stored: bool,
        preflight: ResourcePreflight,
        small_stable: bool,
        busy: bool,
    ) -> None:
        size_mb = manifest.size_bytes / (1024 * 1024)
        self.terms_link.setText(
            self.tr(
                'Current terms: <a href="{url}">{model}</a> — {license}; revision {revision}'
            ).format(
                url=manifest.terms_url,
                model=manifest.model_id,
                license=manifest.license_id,
                revision=manifest.revision[:12],
            )
        )
        state = self.tr("verified and ready") if status.verified else status.issue or "unavailable"
        self.status_label.setText(
            self.tr("{variant}: {size:.1f} MiB; local state: {state}; path: {path}").format(
                variant=manifest.variant.title(), size=size_mb, state=state, path=status.path
            )
        )
        self.acceptance_label.setText(
            self.tr("Accepted for this exact revision") if accepted else self.tr("Not accepted")
        )
        self.token_status.setText(
            self.tr("Token is stored in system credentials")
            if token_stored
            else self.tr("No stored token")
        )
        warnings = "; ".join(preflight.warnings) or self.tr("Resource preflight passed")
        gpu = preflight.snapshot.gpu_name or self.tr("none detected")
        self.resource_label.setText(
            self.tr("RAM free: {ram} MiB; GPU: {gpu}; VRAM free: {vram}; {warnings}").format(
                ram=preflight.snapshot.available_ram_mb,
                gpu=gpu,
                vram=(
                    f"{preflight.snapshot.free_vram_mb} MiB"
                    if preflight.snapshot.free_vram_mb is not None
                    else self.tr("unknown")
                ),
                warnings=warnings,
            )
        )
        medium_allowed = manifest.variant == "small" or small_stable
        self.accept_terms_button.setEnabled(self.terms_reviewed.isChecked() and not busy)
        self.install_button.setEnabled(
            accepted
            and token_stored
            and preflight.can_start
            and medium_allowed
            and not status.installed
            and not busy
        )
        self.delete_model_button.setEnabled(status.installed and not busy)
        self.run_button.setEnabled(
            accepted
            and status.verified
            and preflight.can_start
            and medium_allowed
            and self.rights_confirmed.isChecked()
            and not busy
        )
        self.cancel_button.setEnabled(busy)
        for widget in (
            self.variant,
            self.device,
            self.terms_reviewed,
            self.token,
            self.save_token_button,
            self.delete_token_button,
            self.instruments,
            self.rights_confirmed,
        ):
            widget.setEnabled(not busy)
        if manifest.variant == "medium" and not small_stable:
            self.status_label.setText(
                self.status_label.text()
                + self.tr("; Medium remains disabled until Small is installed and verified")
            )

    def disable_medium_item(self, disabled: bool) -> None:
        model = cast(QStandardItemModel, self.variant.model())
        item = model.item(1)
        if item is not None:
            item.setEnabled(not disabled)

    def _connect_signals(self) -> None:
        self.variant.currentIndexChanged.connect(lambda _index: self.variant_changed.emit())
        self.device.currentIndexChanged.connect(lambda _index: self.device_changed.emit())
        self.terms_reviewed.toggled.connect(
            lambda checked: self.accept_terms_button.setEnabled(checked)
        )
        self.accept_terms_button.clicked.connect(self.accept_terms_requested)
        self.save_token_button.clicked.connect(
            lambda: self.save_token_requested.emit(self.token.text())
        )
        self.delete_token_button.clicked.connect(self.delete_token_requested)
        self.install_button.clicked.connect(self.install_requested)
        self.delete_model_button.clicked.connect(self.delete_model_requested)
        self.run_button.clicked.connect(self.run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.rights_confirmed.toggled.connect(lambda _checked: self.device_changed.emit())
