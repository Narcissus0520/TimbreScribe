"""Connect raw evidence, reviewed settings, and notation application service."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from timbrescribe.application import NotationService
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.ui.notation_workspace import NotationWorkspace


class NotationController(QObject):
    presentation_ready = Signal(object)
    diagnostic = Signal(str)
    status = Signal(str, int)
    error = Signal(str, str, str, str)

    def __init__(
        self,
        workspace: NotationWorkspace,
        service: NotationService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._service = service
        self._raw: RawTranscription | None = None
        workspace.notation_requested.connect(self.generate)

    @property
    def service(self) -> NotationService:
        return self._service

    def set_raw_transcription(self, raw_value: object) -> None:
        if not isinstance(raw_value, RawTranscription):
            return
        self._raw = raw_value
        self._workspace.set_raw_transcription(raw_value)
        self.status.emit(self.tr("Raw evidence is ready for reviewed notation."), 8_000)

    def generate(self) -> None:
        if self._raw is None:
            return
        try:
            presentation = self._service.complete(self._raw, self._workspace.settings_snapshot())
        except (TimbreScribeError, ValueError) as exc:
            self.error.emit(
                self.tr("Notation generation failed"),
                str(exc),
                self.tr("Review tempo, meter, instrument, and quantization settings."),
                "",
            )
            return
        for message in presentation.diagnostics:
            self.diagnostic.emit(message)
        self.presentation_ready.emit(presentation)
        self.status.emit(self.tr("Reviewed notation and Verovio preview generated."), 8_000)
