"""mod_theme.py  v1.5.0
палитры тёмной/светлой темы и QSS для всех окон и диалогов

Журнал:
v1.5.0: строки списка в окне поиска — с отступами.
v1.3.0: вынесено из solar_calc.pyw v1.2.1 (программа была одним файлом)
"""




_QT_THEMES = {
    "dark": {"bg": "#1b1d23", "side": "#16181d", "panel": "#23262e", "panel2": "#2a2e38", "line": "#343946",
             "text": "#e6e8ee", "muted": "#8a91a3", "log_bg": "#111318", "log_fg": "#d5d8e0", "accent": "#4f8cff"},
    "light": {"bg": "#f3f4f7", "side": "#e9ebf0", "panel": "#ffffff", "panel2": "#f1f3f7", "line": "#dde1e8",
              "text": "#1c2230", "muted": "#6b7385", "log_bg": "#fbfbfd", "log_fg": "#1c2230", "accent": "#2f6fe4"}}


_OK, _ERR, _WARN = "#3ecf8e", "#ff5d6c", "#f5b545"


SERIES_COL = {"clear": "#f5b545", "avg": None, "over": "#8a91a3"}


def _qss(p):
    return f"""
* {{ font-family: "Segoe UI"; font-size: 10pt; color: {p['text']}; }}
QMainWindow, QWidget#root {{ background: {p['bg']}; }}
QDialog, QMessageBox, QFileDialog, QInputDialog {{ background: {p['panel']}; color: {p['text']}; }}
QMessageBox QLabel, QDialog QLabel, QFileDialog QLabel, QInputDialog QLabel {{ color: {p['text']}; background: transparent; }}
QDialog QPushButton, QMessageBox QPushButton, QFileDialog QPushButton, QInputDialog QPushButton {{ min-width: 80px; }}
QWidget#page, QWidget#scrollInner, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {p['bg']}; }}
QScrollArea {{ border: none; }}
QFrame#side {{ background: {p['side']}; border-right: 1px solid {p['line']}; }}
QFrame#side QToolButton {{ background: transparent; border: none; border-radius: 9px; font-size: 17pt; padding: 4px; }}
QFrame#side QToolButton:hover {{ background: {p['panel2']}; }}
QFrame#side QToolButton:checked {{ background: {p['panel2']}; border-left: 3px solid {p['accent']}; }}
QFrame#sideSep {{ background: {p['line']}; margin: 4px 6px; }}
QFrame#card {{ background: {p['panel']}; border: 1px solid {p['line']}; border-radius: 10px; }}
QFrame#kpi {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 9px; }}
QLabel {{ background: transparent; }}
QLabel#cardTitle {{ color: {p['muted']}; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#hint, QLabel#muted {{ color: {p['muted']}; font-size: 9pt; }}
QLabel#kpiVal {{ font-size: 16pt; font-weight: 600; }}
QLabel#kpiCap {{ color: {p['muted']}; font-size: 8pt; }}
QLabel#fieldLab {{ color: {p['muted']}; }}
QLabel#subHead {{ color: {p['text']}; font-weight: 600; padding-top: 6px; border-bottom: 1px solid {p['line']}; }}
QLabel#bigTitle {{ font-size: 13pt; font-weight: 600; }}
QFrame#statusbar {{ background: {p['side']}; border-top: 1px solid {p['line']}; }}
QLabel#pill {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 10px; padding: 1px 10px; font-size: 9pt; }}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 7px; padding: 4px 6px;
    selection-background-color: {p['accent']}; selection-color: #ffffff; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {p['accent']}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['panel']}; border: 1px solid {p['line']}; selection-background-color: {p['accent']}; selection-color: #fff; outline: 0; }}
QPushButton {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['line']}; }}
QPushButton:disabled {{ color: {p['muted']}; }}
QPushButton#primary {{ background: {p['accent']}; color: #ffffff; font-weight: 600; border: 1px solid {p['accent']}; }}
QPushButton#primary:hover {{ background: {p['accent']}; border-color: {p['text']}; }}
QPushButton#danger {{ background: transparent; color: {_ERR}; border: 1px solid {_ERR}; }}
QPushButton#chip {{ padding: 3px 10px; font-size: 9pt; border-radius: 11px; }}
QPushButton#seg {{ border-radius: 0; padding: 5px 10px; margin: 0; }}
QPushButton#seg[pos="l"] {{ border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}
QPushButton#seg[pos="r"] {{ border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
QPushButton#seg[pos="s"] {{ border-radius: 7px; }}
QPushButton#seg:checked {{ background: {p['accent']}; color: #ffffff; border-color: {p['accent']}; }}
QToolButton#stepBtn {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 6px; min-width: 22px; max-width: 22px; min-height: 22px; font-weight: 600; }}
QToolButton#stepBtn:hover {{ border-color: {p['accent']}; }}
QAbstractItemView {{ background: {p['panel']}; alternate-background-color: {p['panel2']}; color: {p['text']};
    border: 1px solid {p['line']}; border-radius: 8px; selection-background-color: {p['accent']}; selection-color: #ffffff; }}
QTableWidget {{ gridline-color: transparent; }}
QHeaderView::section {{ background: {p['panel2']}; color: {p['muted']}; border: none; border-bottom: 1px solid {p['line']}; padding: 5px 6px; font-weight: 600; }}
QTableCornerButton::section {{ background: {p['panel2']}; border: none; }}
QPlainTextEdit#log {{ background: {p['log_bg']}; color: {p['log_fg']}; font-family: Consolas, monospace; font-size: 9pt; }}
QMenu {{ background: {p['panel']}; border: 1px solid {p['line']}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {p['accent']}; color: #ffffff; }}
QMenu::item:disabled {{ color: {p['muted']}; }}
QMenu::separator {{ height: 1px; background: {p['line']}; margin: 4px 6px; }}
QToolTip {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['accent']}; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle {{ background: {p['line']}; border-radius: 5px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p['bg']}; }}
QSplitter::handle:hover {{ background: {p['accent']}; }}
QFileDialog QListView, QFileDialog QTreeView {{ background: {p['panel2']}; }}
QDialog QListWidget::item {{ padding: 4px 6px; border-radius: 5px; color: {p['text']}; }}
QDialog QListWidget::item:hover {{ background: {p['panel2']}; }}
QDialog QListWidget::item:selected {{ background: {p['accent']}; color: #ffffff; }}
QFileDialog QToolButton {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 6px; padding: 3px; }}
"""
