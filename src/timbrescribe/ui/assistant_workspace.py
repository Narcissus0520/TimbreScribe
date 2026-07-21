"""Explicit preview-and-confirm surface for the optional score assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AssistantWorkspace(QWidget):
    """Keep provider choice, exact data scope, and confirmation visible."""

    preview_requested = Signal()
    submit_requested = Signal()
    confirm_requested = Signal()
    cancel_requested = Signal()
    save_key_requested = Signal()
    delete_key_requested = Signal()
    input_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.provider = QComboBox(self)
        self.provider.addItem(self.tr("Disabled (core app remains offline)"), "off")
        self.provider.addItem(self.tr("Local llama.cpp / GGUF"), "local")
        self.provider.addItem(self.tr("OpenAI-compatible HTTPS (BYOK)"), "cloud")
        self.provider.setAccessibleName(self.tr("Assistant provider"))

        self.instruction = QPlainTextEdit(self)
        self.instruction.setPlaceholderText(
            self.tr("Example: transpose the selected notes up two semitones")
        )
        self.instruction.setMaximumHeight(90)
        self.instruction.setAccessibleName(self.tr("Assistant instruction"))
        self.selection_label = QLabel(self.tr("No score selection is available."), self)
        self.selection_label.setWordWrap(True)
        self.use_measure_range = QCheckBox(self.tr("Limit context to measures"), self)
        self.measure_start = QSpinBox(self)
        self.measure_start.setRange(1, 100_000)
        self.measure_end = QSpinBox(self)
        self.measure_end.setRange(1, 100_000)
        self.measure_start.setValue(1)
        self.measure_end.setValue(1)
        measure_row = QHBoxLayout()
        measure_row.addWidget(self.measure_start)
        measure_row.addWidget(QLabel(self.tr("through"), self))
        measure_row.addWidget(self.measure_end)
        measure_row.addStretch(1)

        self.request_group = QGroupBox(self.tr("Instruction and minimized scope"), self)
        request_layout = QFormLayout(self.request_group)
        request_layout.addRow(self.tr("Provider"), self.provider)
        request_layout.addRow(self.tr("Instruction"), self.instruction)
        request_layout.addRow(self.tr("Current selection"), self.selection_label)
        request_layout.addRow(self.use_measure_range, measure_row)

        self.local_executable = QLineEdit(self)
        self.local_model = QLineEdit(self)
        self.local_model_id = QLineEdit(self)
        self.local_model_id.setText("qwen-4b-class-gguf")
        self.local_executable.setAccessibleName(self.tr("llama-server executable path"))
        self.local_model.setAccessibleName(self.tr("Local GGUF model path"))
        browse_server = QPushButton(self.tr("Browse…"), self)
        browse_model = QPushButton(self.tr("Browse…"), self)
        server_row = QHBoxLayout()
        server_row.addWidget(self.local_executable, 1)
        server_row.addWidget(browse_server)
        model_row = QHBoxLayout()
        model_row.addWidget(self.local_model, 1)
        model_row.addWidget(browse_model)
        self.local_notice = QLabel(
            self.tr(
                "Recommended: a user-supplied Qwen 4B-class GGUF. TimbreScribe does not "
                "download or redistribute model weights."
            ),
            self,
        )
        self.local_notice.setWordWrap(True)
        self.local_group = QGroupBox(self.tr("Local provider"), self)
        local_layout = QFormLayout(self.local_group)
        local_layout.addRow(self.tr("llama-server"), server_row)
        local_layout.addRow(self.tr("GGUF model"), model_row)
        local_layout.addRow(self.tr("Model ID"), self.local_model_id)
        local_layout.addRow(self.local_notice)

        self.cloud_endpoint = QLineEdit(self)
        self.cloud_endpoint.setText("https://api.openai.com/v1/chat/completions")
        self.cloud_model = QLineEdit(self)
        self.api_key = QLineEdit(self)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setAccessibleName(self.tr("Cloud assistant API key"))
        self.save_key_button = QPushButton(self.tr("Save key to OS credential store"), self)
        self.delete_key_button = QPushButton(self.tr("Delete stored key"), self)
        key_row = QHBoxLayout()
        key_row.addWidget(self.save_key_button)
        key_row.addWidget(self.delete_key_button)
        key_row.addStretch(1)
        self.key_status = QLabel(self.tr("Key status has not been checked."), self)
        self.cloud_group = QGroupBox(self.tr("Cloud provider"), self)
        cloud_layout = QFormLayout(self.cloud_group)
        cloud_layout.addRow(self.tr("HTTPS endpoint"), self.cloud_endpoint)
        cloud_layout.addRow(self.tr("Model ID"), self.cloud_model)
        cloud_layout.addRow(self.tr("API key"), self.api_key)
        cloud_layout.addRow(key_row)
        cloud_layout.addRow(self.key_status)

        self.preview_button = QPushButton(self.tr("Preview exact provider data"), self)
        self.submit_button = QPushButton(self.tr("Send previewed request"), self)
        self.submit_button.setEnabled(False)
        request_actions = QHBoxLayout()
        request_actions.addWidget(self.preview_button)
        request_actions.addWidget(self.submit_button)
        request_actions.addStretch(1)
        self.cloud_consent = QCheckBox(
            self.tr(
                "I approve sending exactly the project/request JSON shown below to this "
                "cloud endpoint."
            ),
            self,
        )
        self.cloud_consent.setEnabled(False)
        self.privacy_notice = QLabel(
            self.tr(
                "Only note IDs and summaries, measure scope, key, meter, tempo, instrument, "
                "and your instruction may be sent. Audio, video, project archives, paths, "
                "credentials, and unrelated project data are never included."
            ),
            self,
        )
        self.privacy_notice.setWordWrap(True)
        self.data_preview = QPlainTextEdit(self)
        self.data_preview.setReadOnly(True)
        self.data_preview.setPlaceholderText(
            self.tr("Nothing can be sent until the exact minimized JSON is previewed here.")
        )
        self.data_preview.setAccessibleName(self.tr("Exact provider data preview"))
        preview_group = QGroupBox(self.tr("Privacy review"), self)
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.addWidget(self.privacy_notice)
        preview_layout.addLayout(request_actions)
        preview_layout.addWidget(self.cloud_consent)
        preview_layout.addWidget(self.data_preview)

        self.result = QPlainTextEdit(self)
        self.result.setReadOnly(True)
        self.result.setPlaceholderText(
            self.tr("Validated explanations or deterministic project changes appear here.")
        )
        self.result.setAccessibleName(self.tr("Assistant validated result"))
        self.confirm_button = QPushButton(self.tr("Confirm project changes"), self)
        self.cancel_button = QPushButton(self.tr("Discard proposal"), self)
        self.confirm_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        result_actions = QHBoxLayout()
        result_actions.addWidget(self.confirm_button)
        result_actions.addWidget(self.cancel_button)
        result_actions.addStretch(1)
        result_group = QGroupBox(self.tr("Validated result and deterministic diff"), self)
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self.result)
        result_layout.addLayout(result_actions)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(self.request_group)
        body_layout.addWidget(self.local_group)
        body_layout.addWidget(self.cloud_group)
        body_layout.addWidget(preview_group)
        body_layout.addWidget(result_group)
        body_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

        self.provider.currentIndexChanged.connect(self._configuration_changed)
        self.instruction.textChanged.connect(self.input_changed)
        self.use_measure_range.toggled.connect(self._configuration_changed)
        self.measure_start.valueChanged.connect(self.input_changed)
        self.measure_end.valueChanged.connect(self.input_changed)
        for field in (
            self.local_executable,
            self.local_model,
            self.local_model_id,
            self.cloud_endpoint,
            self.cloud_model,
        ):
            field.textChanged.connect(self.input_changed)
        browse_server.clicked.connect(self._browse_server)
        browse_model.clicked.connect(self._browse_model)
        self.preview_button.clicked.connect(self.preview_requested)
        self.submit_button.clicked.connect(self.submit_requested)
        self.confirm_button.clicked.connect(self.confirm_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.save_key_button.clicked.connect(self.save_key_requested)
        self.delete_key_button.clicked.connect(self.delete_key_requested)
        self.cloud_consent.toggled.connect(self._update_submit_enabled)
        self._has_preview = False
        self._busy = False
        self._configuration_changed()

    @property
    def provider_mode(self) -> Literal["off", "local", "cloud"]:
        value = self.provider.currentData()
        return cast(Literal["off", "local", "cloud"], value)

    @property
    def measure_range(self) -> tuple[int, int] | None:
        if not self.use_measure_range.isChecked():
            return None
        return (self.measure_start.value(), self.measure_end.value())

    def apply_settings(
        self,
        *,
        provider_mode: str,
        local_executable: str,
        local_model: str,
        local_model_id: str,
        cloud_endpoint: str,
        cloud_model: str,
    ) -> None:
        index = self.provider.findData(provider_mode)
        self.provider.setCurrentIndex(max(0, index))
        self.local_executable.setText(local_executable)
        self.local_model.setText(local_model)
        self.local_model_id.setText(local_model_id)
        self.cloud_endpoint.setText(cloud_endpoint)
        self.cloud_model.setText(cloud_model)
        self._configuration_changed()

    def set_selection_count(self, count: int) -> None:
        self.selection_label.setText(
            self.tr("{count} selected note IDs will be eligible for the preview.").format(
                count=count
            )
            if count
            else self.tr("Select notes or enable an explicit measure range before previewing.")
        )

    def set_preview(self, value: str) -> None:
        self.data_preview.setPlainText(value)
        self._has_preview = True
        self.cloud_consent.setChecked(False)
        self._update_submit_enabled()

    def clear_review(self) -> None:
        self._has_preview = False
        self.data_preview.clear()
        self.cloud_consent.setChecked(False)
        self.result.clear()
        self.confirm_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self._update_submit_enabled()

    def show_plan(self, text: str, *, can_confirm: bool, destructive: bool) -> None:
        prefix = self.tr("DESTRUCTIVE CHANGE — review every line.\n\n") if destructive else ""
        self.result.setPlainText(prefix + text)
        self.confirm_button.setEnabled(can_confirm and not self._busy)
        self.cancel_button.setEnabled(not self._busy)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.preview_button.setEnabled(not busy and self.provider_mode != "off")
        self.provider.setEnabled(not busy)
        self.instruction.setEnabled(not busy)
        self.use_measure_range.setEnabled(not busy)
        self.measure_start.setEnabled(not busy)
        self.measure_end.setEnabled(not busy)
        self.local_group.setEnabled(not busy and self.provider_mode == "local")
        self.cloud_group.setEnabled(not busy and self.provider_mode == "cloud")
        self.confirm_button.setEnabled(False if busy else self.confirm_button.isEnabled())
        self.cancel_button.setEnabled(False if busy else self.cancel_button.isEnabled())
        self._update_submit_enabled()

    def set_key_status(self, text: str) -> None:
        self.key_status.setText(text)

    def _configuration_changed(self) -> None:
        mode = self.provider_mode
        self.local_group.setEnabled(mode == "local")
        self.cloud_group.setEnabled(mode == "cloud")
        self.cloud_consent.setEnabled(mode == "cloud" and self._has_preview and not self._busy)
        self.preview_button.setEnabled(mode != "off" and not self._busy)
        self.input_changed.emit()
        self._update_submit_enabled()

    def _update_submit_enabled(self) -> None:
        allowed = self._has_preview and not self._busy and self.provider_mode != "off"
        if self.provider_mode == "cloud":
            allowed = allowed and self.cloud_consent.isChecked()
        self.submit_button.setEnabled(allowed)
        self.cloud_consent.setEnabled(
            self.provider_mode == "cloud" and self._has_preview and not self._busy
        )

    def _browse_server(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose llama-server executable"),
            str(Path(self.local_executable.text()).parent) if self.local_executable.text() else "",
            self.tr("Executables (*.exe);;All files (*)"),
        )
        if filename:
            self.local_executable.setText(filename)

    def _browse_model(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose local GGUF model"),
            str(Path(self.local_model.text()).parent) if self.local_model.text() else "",
            self.tr("GGUF models (*.gguf)"),
        )
        if filename:
            self.local_model.setText(filename)
