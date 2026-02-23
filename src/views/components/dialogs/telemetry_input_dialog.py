import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from src.views.components.widgets.step_control import StepControl


class TelemetryInputDialog(QDialog):
    """
    Dialog for manual telemetry paste/clean/format/save workflow.

    Flow:
    1) Paste raw line-wrapped telemetry payload with optional D: prefixes.
    2) Click Format to normalize and pretty-print JSON.
    3) Click Save to emit a validated event object to the controller.
    """

    save_requested = Signal(dict)

    def __init__(self, parent=None, step_manager=None):
        super().__init__(parent)
        self._step_manager = step_manager
        self._parsed_event = None
        self._build_ui()
        self._wire_signals()

    @property
    def parsed_event(self):
        return self._parsed_event

    def _build_ui(self):
        self.setWindowTitle("Telemetry Input")
        self.setMinimumSize(980, 640)
        self.resize(1080, 720)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Telemetry Input")
        title.setObjectName("SectionHeader")
        root.addWidget(title)

        subtitle = QLabel(
            "Paste raw telemetry output, clean D: prefixes, then format and save as JSON."
        )
        subtitle.setObjectName("PlaceholderText")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        root.addLayout(top_row)

        step_label = QLabel("Step")
        step_label.setObjectName("FieldLabel")
        top_row.addWidget(step_label)

        self.step_control = StepControl()
        self.step_control.setFixedWidth(140)
        if self._step_manager is not None:
            self.step_control.connect_to_manager(self._step_manager)
        top_row.addWidget(self.step_control)
        top_row.addStretch(1)

        panes = QHBoxLayout()
        panes.setSpacing(12)
        root.addLayout(panes, 1)

        left_panel = QFrame()
        left_panel.setObjectName("TelemetryInputPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        raw_label = QLabel("Raw Telemetry")
        raw_label.setObjectName("FieldLabel")
        left_layout.addWidget(raw_label)

        self.raw_editor = QPlainTextEdit()
        self.raw_editor.setPlaceholderText(
            "Paste raw payload here...\nExample line prefix: D:{\"eventCategory\": ... }"
        )
        self.raw_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_editor.setTabStopDistance(32)
        left_layout.addWidget(self.raw_editor, 1)

        right_panel = QFrame()
        right_panel.setObjectName("TelemetryInputPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        formatted_label = QLabel("Formatted JSON")
        formatted_label.setObjectName("FieldLabel")
        right_layout.addWidget(formatted_label)

        self.formatted_editor = QPlainTextEdit()
        self.formatted_editor.setReadOnly(True)
        self.formatted_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.formatted_editor.setTabStopDistance(32)
        right_layout.addWidget(self.formatted_editor, 1)

        panes.addWidget(left_panel, 1)
        panes.addWidget(right_panel, 1)

        self.status_label = QLabel("Paste telemetry and click Format.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setProperty("type", "warning")
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        root.addLayout(actions)

        self.btn_format = QPushButton("Clean + Format")
        self.btn_format.setObjectName("PrimaryButton")
        actions.addWidget(self.btn_format)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("GhostButton")
        actions.addWidget(self.btn_clear)

        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("ActionKey")
        self.btn_save.setEnabled(False)
        actions.addWidget(self.btn_save)

        self.setStyleSheet(
            """
            QFrame#TelemetryInputPanel {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            """
        )

    def _wire_signals(self):
        self.btn_close.clicked.connect(self.close)
        self.btn_format.clicked.connect(self._on_format)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_save.clicked.connect(self._on_save)
        self.raw_editor.textChanged.connect(self._on_raw_changed)

    def _set_status(self, message: str, status_type: str) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("type", status_type)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _on_raw_changed(self):
        # Any edit invalidates the last parsed payload.
        self._parsed_event = None
        self.btn_save.setEnabled(False)

    def _on_format(self):
        raw_text = self.raw_editor.toPlainText()
        if not raw_text.strip():
            self.formatted_editor.clear()
            self._set_status("No telemetry text detected.", "error")
            return

        try:
            normalized_json = self._normalize_raw_payload(raw_text)
            payload = json.loads(normalized_json)
            self._validate_payload(payload)
        except ValueError as exc:
            self._parsed_event = None
            self.btn_save.setEnabled(False)
            self._set_status(str(exc), "error")
            return
        except json.JSONDecodeError as exc:
            self._parsed_event = None
            self.btn_save.setEnabled(False)
            self._set_status(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                "error",
            )
            return

        self._parsed_event = payload
        self.formatted_editor.setPlainText(json.dumps(payload, indent=4))
        self.btn_save.setEnabled(True)
        self._set_status("Telemetry parsed and formatted. Ready to save.", "success")

    def _on_save(self):
        if not self._parsed_event:
            self._set_status("Format telemetry before saving.", "error")
            return

        self.save_requested.emit(self._parsed_event)
        self._set_status("Save request sent.", "success")

    def _on_clear(self):
        self.raw_editor.clear()
        self.formatted_editor.clear()
        self._parsed_event = None
        self.btn_save.setEnabled(False)
        self._set_status("Paste telemetry and click Format.", "warning")

    @staticmethod
    def _normalize_raw_payload(raw_text: str) -> str:
        parts = []
        for line in raw_text.splitlines():
            piece = line.strip()
            if not piece:
                continue
            if piece.startswith("D:"):
                piece = piece[2:].strip()
            parts.append(piece)

        merged = "".join(parts).strip()
        if not merged:
            raise ValueError("No payload content detected after cleanup.")

        start_idx = merged.find("{")
        end_idx = merged.rfind("}")
        if start_idx < 0 or end_idx < 0 or end_idx < start_idx:
            raise ValueError("Could not locate a valid JSON object in the input.")

        return merged[start_idx : end_idx + 1]

    @staticmethod
    def _validate_payload(payload):
        if not isinstance(payload, dict):
            raise ValueError("Telemetry payload must be a JSON object.")

        event_detail = payload.get("eventDetail")
        if not isinstance(event_detail, dict):
            raise ValueError("Telemetry payload missing required object: eventDetail.")
