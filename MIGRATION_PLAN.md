# Migration Plan: Tkinter to PySide6

This plan outlines the steps to convert the application to PySide6 while maintaining a working Tkinter version during the transition ("Small Chunks" approach).

## 1. Architecture & File Structure (Completed)
- [x] Create `src/ui_qt/` structure.
- [x] Implement `styles.qss` (Dark Mode Theme).
- [x] Implement `main_qt.py` entry point.
- [x] Implement `QtTabContent` base class (Composition/Lifecycle hooks).

## 2. Core Components (Completed)
- [x] **Navigation Bar**: `NavBar` with custom `ModernButton`.
- [x] **Config Bar**: IP and Directory inputs.
- [x] **Alerts Widget**: Reusable `QTreeWidget` with context menu.
- [x] **Telemetry Widget**: Reusable `QTreeWidget` with dual-format support.
- [x] **Worker Threads**: `FetchAlertsWorker` and `FetchTelemetryWorker`.

## 3. Tab Implementation Status

### Ares Tab (In Progress)
- [x] Layout: Splitter with Alerts/Telemetry.
- [x] Logic: Background fetching via Workers.
- [ ] **Pending**: VNC/EWS Capture features (Needs VNC Port).
- [x] **Pending**: CDM Controls (Checkboxes).

### Settings Tab (Pending)
- [x] Basic Shell.
- [ ] **Next**: Implement ConfigManager loading/saving.

### Dune Tab (Pending)
- [ ] **Critical**: Port `vncapp.py` to use `QImage`/`QPixmap` instead of Tkinter.
- [ ] Implement Mouse/Keyboard event mapping.

### Sirius Tab (Pending)
- [ ] Port Sirius-specific logic using the new Base Class.

## 4. Next Immediate Steps (For New Chat)
1.  **Settings Tab**: Make the "Save" button actually write to `config.json`.
2.  **VNC Refactor**: The big one. Modify `vncapp.py` to return raw bytes or PIL images without Tkinter deps, then build `QtVNCWidget`.
3.  **Dune Tab**: Assemble the VNC widget into the Dune tab.

## 5. Final Cleanup
- [x] Remove legacy `main.py` entry (Qt app only).
- [x] Delete `src/ui` package.
- [ ] Rename `main_qt.py` to `main.py`.

