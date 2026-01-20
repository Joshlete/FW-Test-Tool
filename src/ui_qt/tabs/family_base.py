from PySide6.QtWidgets import (QVBoxLayout, QFrame, QSplitter, QSplitterHandle, QLabel)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPainter, QPen, QColor
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget

class FamilySplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.SplitHCursor if orientation == Qt.Orientation.Horizontal else Qt.CursorShape.SplitVCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        line_color = QColor(100, 100, 100)
        pen = QPen(line_color, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        if self.orientation() == Qt.Orientation.Horizontal:
            center_x = self.width() // 2
            painter.drawLine(center_x, 10, center_x, self.height() - 10)
        else:
            center_y = self.height() // 2
            painter.drawLine(10, center_y, self.width() - 10, center_y)


class FamilySplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(8)

    def createHandle(self):
        return FamilySplitterHandle(self.orientation(), self)


class FamilyTabBase(QtTabContent):
    """
    Base class for family tabs (Dune, Sirius, etc.)
    Implements the standard 3-column layout:
    - Left: Data Control (CDM/LEDM)
    - Center: Manual Ops + Printer View
    - Right: Alerts + Telemetry
    """

    def __init__(self, tab_name, config_manager, controllers=None):
        super().__init__(tab_name=tab_name, config_manager=config_manager)
        
        self.config_manager = config_manager
        self._controllers = controllers or {}
        self.ip = None
        
        # Initialize Layout
        self._init_layout()
        
        # Restore Splitter State (must be done after init_layout so splitters exist)
        self._restore_splitter_state()
        
        # Wire common controllers (Alerts, Telemetry)
        self._wire_base_controllers()

    def _init_layout(self):
        """Initialize the 3-column layout."""
        self.main_splitter = FamilySplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.main_splitter)
        
        # 1. Left Column: Data Control
        self._setup_left_column()
        
        # 2. Center Column: Manual Ops + Printer View
        self._setup_center_column()
        
        # 3. Right Column: Alerts + Telemetry
        self._setup_right_column()
        
        # Set Initial Stretch Factors (25%, 35%, 40% approx)
        self.main_splitter.setStretchFactor(0, 25)
        self.main_splitter.setStretchFactor(1, 35)
        self.main_splitter.setStretchFactor(2, 40)

    def _setup_left_column(self):
        """Override to setup the left column (Data Control)."""
        raise NotImplementedError

    def _setup_center_column(self):
        """Override to setup the center column (Manual Ops + Printer View)."""
        raise NotImplementedError

    def _setup_right_column(self):
        """Initialize the right column with Alerts and Telemetry (Common)."""
        right_container = QFrame()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for Alerts/Telemetry
        self.right_splitter = FamilySplitter(Qt.Orientation.Vertical)
        
        # Alerts
        # We wrap in a card-like frame in the concrete implementation or here?
        # The plan says "Creates common Right Column (Alerts + Telemetry)" in base.
        # It also mentions "AlertsCard" in the diagram but "AlertsWidget" in text.
        # "Modify src/ui_qt/tabs/dune.py ... Remove code now handled by base class (Alerts/Telemetry init)"
        
        # I'll create containers here.
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setObjectName("SectionHeader")
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # Telemetry
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setObjectName("SectionHeader")
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        self.right_splitter.addWidget(alerts_container)
        self.right_splitter.addWidget(telemetry_container)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 1)
        
        right_layout.addWidget(self.right_splitter)
        self.main_splitter.addWidget(right_container)

    def _wire_base_controllers(self):
        """Wire Alerts and Telemetry controllers."""
        
        # --- Alerts Controller ---
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
            # Action wiring might depend on family, but we can wire the signal 
            # and let the controller handle/ignore.
            # Dune uses 'send_action', Sirius might not.
            # Actually, standard AlertsWidget emits action_requested(id, action).
            # The controller should have send_action.
            if hasattr(alerts_ctrl, 'send_action'):
                self.alerts_widget.action_requested.connect(
                    lambda alert_id, action: alerts_ctrl.send_action(int(alert_id), action)
                )

        # --- Telemetry Controller ---
        telemetry_ctrl = self._controllers.get('telemetry')
        if telemetry_ctrl:
            if self.step_manager:
                telemetry_ctrl.set_step_manager(self.step_manager)
            
            # Note: Dune needs is_dune_format=True, Sirius doesn't.
            # We might need a flag or override this wiring.
            # For now, I'll bind generic signals. The population logic might need an override or config.
            # The plan says "FamilyTabBase... Handles common controller wiring".
            # But DuneTab has `is_dune_format=True`.
            # I can make a method `_on_telemetry_updated` that can be overridden or configured.
            
            telemetry_ctrl.telemetry_updated.connect(self._on_telemetry_updated)
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)

    def _on_telemetry_updated(self, events):
        """Handle telemetry updates. Can be overridden."""
        # Default behavior (Sirius)
        self.telemetry_widget.populate_telemetry(events)

    def _restore_splitter_state(self):
        """Restore splitter state from config. Override/Implement in subclasses or here with dynamic keys."""
        pass
