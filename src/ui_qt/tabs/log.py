from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)
from PySide6.QtCore import Qt
from .base import QtTabContent
from src.utils.logging.app_logger import clear_recent_logs, get_recent_logs, get_log_signaler
import json


class LogTab(QtTabContent):
    """Display recent log entries in a modern card-style layout."""

    def __init__(self):
        super().__init__()

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        title = QLabel("Application Log")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title)

        controls = QHBoxLayout()
        controls.setSpacing(12)

        self.level_filter = QComboBox()
        self.level_filter.addItems(["All", "Info", "Warning", "Error", "Debug"])

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search message or action...")

        self.clear_btn = QPushButton("Clear Log")

        controls.addWidget(QLabel("Level"))
        controls.addWidget(self.level_filter)
        controls.addWidget(self.search_box, 1)
        controls.addWidget(self.clear_btn)

        card_layout.addLayout(controls)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Time", "Level", "Action", "Message"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        card_layout.addWidget(self.tree, 2)

        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setFixedHeight(160)
        self.detail_box.setPlaceholderText("Select a log entry to view details...")
        card_layout.addWidget(self.detail_box)

        self.layout.addWidget(card)

        # Signals
        self.clear_btn.clicked.connect(self._clear_log)
        self.level_filter.currentIndexChanged.connect(self._populate_initial_logs)
        self.search_box.textChanged.connect(self._populate_initial_logs)
        self.tree.itemSelectionChanged.connect(self._update_detail_panel)

        # Connect to Logger Bridge
        self.log_signaler = get_log_signaler()
        self.log_signaler.log_added.connect(self._on_new_log_entry)

        # Populate initial data
        self._populate_initial_logs()

    def _populate_initial_logs(self):
        """Rebuilds the whole list (e.g. on filter change or show)."""
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        self.detail_box.clear()
        
        entries = get_recent_logs()
        # We want newest first, so we iterate normally (get_recent_logs is [newest...oldest])
        # Wait, app_logger appends left, so snapshot is [newest, ... oldest]
        # But usually we want to read logs top-down? Let's stick to newest-at-top for monitoring
        
        for entry in entries:
            if self._should_show(entry):
                self._add_tree_item(entry)
                
        self._resize_columns()
        self.tree.setUpdatesEnabled(True)

    def _on_new_log_entry(self, entry):
        """Called incrementally when a log occurs."""
        if not self._should_show(entry):
            return
            
        # Add to top
        self._add_tree_item(entry, index=0)
        self._resize_columns()

    def _add_tree_item(self, entry, index=None):
        item = QTreeWidgetItem(
            [
                entry.timestamp.strftime("%H:%M:%S"),
                entry.level,
                entry.action or entry.status,
                entry.message,
            ]
        )
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        
        if index is not None:
            self.tree.insertTopLevelItem(index, item)
        else:
            self.tree.addTopLevelItem(item)

    def _should_show(self, entry):
        level_filter = self.level_filter.currentText().lower()
        query = self.search_box.text().lower().strip()

        if level_filter != "all" and entry.level.lower() != level_filter:
            return False
            
        if query:
            text_blob = " ".join(
                [
                    entry.message.lower(),
                    entry.action.lower(),
                    entry.status.lower(),
                    json.dumps(entry.details, default=str).lower() if entry.details else "",
                ]
            )
            if query not in text_blob:
                return False
                
        return True

    def _resize_columns(self):
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)

    def _update_detail_panel(self):
        selected = self.tree.selectedItems()
        if not selected:
            self.detail_box.clear()
            return

        entry = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not entry:
            self.detail_box.clear()
            return

        details = (entry.details or {}).copy()
        returned_data = details.pop("returned", None)
        
        pretty = json.dumps(details, indent=2, default=str) if details else "No details."
        
        rendered = (
            f"Timestamp: {entry.timestamp.isoformat()}\n"
            f"Level: {entry.level}\n"
            f"Action: {entry.action}\n"
            f"Status: {entry.status}\n"
            f"Message: {entry.message}\n\n"
            f"Details:\n{pretty}"
        )
        
        if returned_data is not None:
            pretty_returned = json.dumps(returned_data, indent=2, default=str)
            rendered += f"\n\nReturned:\n{pretty_returned}"

        self.detail_box.setPlainText(rendered)

    def _clear_log(self):
        clear_recent_logs()
        self.tree.clear()
        self.detail_box.clear()

    def on_show(self):
        # Optional: auto-refresh if we missed signals while hidden?
        # For now, since signals are app-wide, we receive them even if hidden.
        # But we might want to re-sync if we assume signals only fire on active.
        # Actually, QSignals fire regardless. 
        # Just in case, let's do a full refresh to be safe and strictly ordered.
        self._populate_initial_logs()

    def on_hide(self):
        pass
