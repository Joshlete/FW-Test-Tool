"""Token-driven dark theme for the prototype UI.
macOS-inspired contrast hierarchy: app (darkest) → cards (mid) → inputs/log (lighter).
"""

from __future__ import annotations

import os

# Design tokens — tonal hierarchy
APP_BG = "#0D0F12"           # Darkest: app background
PANEL = "#21262D"            # Cards and panels (Significant lift for separation)
ELEVATED = "#30363D"         # Raised: buttons, combo base
INK_TILE_BG = "#30363D"      # Tile surface (Aligned with ELEVATED)
SURFACE_INPUT = "#30363D"    # Input/log surfaces (Aligned with ELEVATED)
INK_TRACK_BG = "#586069"     # Progress track (contrast against tile)
TEXT_PRIMARY = "#EBEEF3"
TEXT_SECONDARY = "#B2BDCC"
TEXT_MUTED = "#7E8A9C"
BORDER = "#485260"           # Stronger card/control edges for glare visibility
BORDER_HOVER = "#6E7681"     # Distinct hover state
ACCENT = "#4C8DFF"
SUCCESS = "#39D98A"
WARNING = "#F5B84D"
DANGER = "#FF5D73"

ASSETS_DIR = os.path.dirname(__file__).replace("\\", "/") + "/assets"

# Status badge tokens (semantic success/warning/neutral for connection/drain labels)
STATUS_SUCCESS_BG = "rgba(57, 217, 138, 0.15)"
STATUS_SUCCESS_FG = SUCCESS
STATUS_SUCCESS_BORDER = "rgba(57, 217, 138, 0.25)"
STATUS_WARNING_BG = "rgba(245, 184, 77, 0.15)"
STATUS_WARNING_FG = WARNING
STATUS_WARNING_BORDER = "rgba(245, 184, 77, 0.25)"
STATUS_NEUTRAL_BG = "rgba(182, 192, 207, 0.1)"
STATUS_NEUTRAL_FG = TEXT_SECONDARY
STATUS_NEUTRAL_BORDER = "rgba(182, 192, 207, 0.2)"

# Ink color accents (Black, Cyan, Magenta, Yellow) — approved palette
INK_BLACK = "#A7B0BF"
INK_CYAN = "#2ECFFF"
INK_MAGENTA = "#FF4FCF"
INK_YELLOW = "#FFD84D"

# Legacy aliases for inline styles (cards use theme.TEXT_SECONDARY, etc.)
WINDOW_BACKGROUND = APP_BG
CARD_BACKGROUND = PANEL
CARD_BORDER = BORDER


def build_stylesheet() -> str:
    return f"""
QMainWindow {{
    background-color: {APP_BG};
}}
QWidget {{
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Helvetica Neue", "Arial", sans-serif;
    font-size: 13px;
}}
QFrame#Card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#CardTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
QLabel#CardSubtitle {{
    color: {TEXT_SECONDARY};
}}
QPushButton {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 34px;
}}
QPushButton:hover {{
    background-color: {SURFACE_INPUT};
    border-color: {BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {BORDER};
}}
QPushButton:focus {{
    border-color: {ACCENT};
    outline: none;
}}
QPushButton:disabled {{
    background-color: {PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton#PrimaryButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
}}
QPushButton#PrimaryButton:hover {{
    background-color: #6BA0FF;
    border-color: #6BA0FF;
}}
QPushButton#PrimaryButton:pressed {{
    background-color: #3D7AFF;
}}
QPushButton#PrimaryButton:focus {{
    border-color: #80B0FF;
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton#SecondaryButton {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
}}
QPushButton#SecondaryButton:hover {{
    background-color: {SURFACE_INPUT};
    border-color: {BORDER_HOVER};
}}
QPushButton#SecondaryButton:pressed {{
    background-color: {BORDER};
}}
QPushButton#DangerButton {{
    background-color: {DANGER};
    color: #ffffff;
    border: 1px solid {DANGER};
}}
QPushButton#DangerButton:hover {{
    background-color: #FF7A8A;
}}
QPushButton#DangerButton:pressed {{
    background-color: #E64D63;
}}
QPushButton#DangerButton:focus {{
    border-color: #FF8A98;
}}
QPushButton#DangerButton:disabled {{
    background-color: {PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QLineEdit, QComboBox, QSpinBox {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    min-height: 34px;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border-color: {BORDER_HOVER};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background-color: {PANEL};
    color: {TEXT_MUTED};
}}
QComboBox {{
    padding-right: 32px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background: {ELEVATED};
}}
QComboBox::down-arrow {{
    image: url({ASSETS_DIR}/chevron-down.svg);
    width: 16px;
    height: 16px;
    margin-right: 2px;
}}
QComboBox QAbstractItemView {{
    background-color: {ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
    padding: 2px;
}}
QComboBox::item {{
    height: 24px;
}}
QComboBox::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {BORDER};
    height: 8px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {ACCENT};
}}
QWidget#InkTile {{
    background-color: {INK_TILE_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QProgressBar#InkBar {{
    background-color: {INK_TRACK_BG};
    border: none;
    border-radius: 3px;
}}
QProgressBar#InkBar::chunk {{
    border-radius: 3px;
}}
QPlainTextEdit#LogArea {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    padding: 8px;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: 12px;
}}
QPlainTextEdit#LogArea:focus {{
    border-color: {ACCENT};
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {BORDER_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QSplitter {{
    background-color: transparent;
    spacing: 6px;
}}
QSplitter::handle {{
    background-color: {BORDER};
    image: none;
}}
QSplitter::handle:horizontal {{
    width: 6px;
    image: none;
    border-left: 2px solid {APP_BG};
    border-right: 2px solid {APP_BG};
}}
QSplitter::handle:horizontal:hover, QSplitter::handle:horizontal:pressed {{
    background-color: {ACCENT};
    border-left: 1px solid {APP_BG};
    border-right: 1px solid {APP_BG};
}}
QSplitter::handle:vertical {{
    height: 6px;
    image: none;
    border-top: 2px solid {APP_BG};
    border-bottom: 2px solid {APP_BG};
}}
QSplitter::handle:vertical:hover, QSplitter::handle:vertical:pressed {{
    background-color: {ACCENT};
    border-top: 1px solid {APP_BG};
    border-bottom: 1px solid {APP_BG};
}}
QFormLayout QLabel {{
    color: {TEXT_SECONDARY};
}}
"""
