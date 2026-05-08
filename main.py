import argparse
import csv
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
TITLE_PATTERN = re.compile(r"DCR(?P<dcr>-?\d+(?:\.\d+)?)" r".*?PDE(?P<pde>-?\d+(?:\.\d+)?)" r".*?APP(?P<app>-?\d+(?:\.\d+)?)", re.IGNORECASE)
TEMP_PATTERN = re.compile(r"TEMP(?P<temp>-?\d+(?:\.\d+)?)", re.IGNORECASE)
GATE_PATTERN = re.compile(r"GATE(?P<gate>-?\d+(?:\.\d+)?)", re.IGNORECASE)
@dataclass
class DataPoint:
    pde_percent: float
    dcr_k: float
    app_percent: float
    source_file: Path
@dataclass
class NoteConfig:
    enabled: bool = True
    text: str = "Custom Note"
    loc: str = "upper left"
    x: float = 0.03
    y: float = 0.97
    ha: str = "left"
    va: str = "top"
    fontsize: int = 11
def parse_metrics_from_title(text: str) -> Optional[Tuple[float, float, float]]:
    m = TITLE_PATTERN.search(text)
    if not m:
        return None
    dcr_k = float(m.group("dcr")) / 1000.0
    return float(m.group("pde")), dcr_k, float(m.group("app"))
def extract_title_from_csv(file_path: Path) -> Optional[str]:
    for encoding in ("utf-8-sig", "gbk"):
        try:
            with file_path.open("r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader):
                    if idx > 30:
                        break
                    merged = "-".join(cell.strip() for cell in row if cell and cell.strip())
                    up = merged.upper()
                    if "DCR" in up and "PDE" in up and "APP" in up:
                        return merged
        except Exception:
            pass
    return None
def parse_file_to_point(file_path: Path) -> Optional[DataPoint]:
    candidates = []
    content_title = extract_title_from_csv(file_path)
    if content_title:
        candidates.append(content_title)
    candidates.extend([file_path.stem, file_path.name])
    for text in candidates:
        parsed = parse_metrics_from_title(text)
        if parsed:
            pde, dcr_k, app = parsed
            return DataPoint(pde, dcr_k, app, file_path)
    return None
def run_self_test() -> int:
    sample = "Temp-20-Bias67.5-Gate16-DCR1000-PDE22.38-APP0.53-20260427"
    parsed = parse_metrics_from_title(sample)
    assert parsed is not None
    pde, dcr_k, app = parsed
    assert abs(pde - 22.38) < 1e-9
    assert abs(dcr_k - 1.0) < 1e-9
    assert abs(app - 0.53) < 1e-9
    assert TEMP_PATTERN.search(sample)
    assert GATE_PATTERN.search(sample)
    print("Self-test passed.")
    return 0
def launch_gui() -> int:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QSplitter,
        QTabWidget,
        QVBoxLayout,
        QWidget,
        QTextEdit,
    )
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    class MatplotlibCanvas(FigureCanvas):
        def __init__(self, title: str, x_label: str, y_label: str, parent=None):
            self.figure = Figure()
            self.ax = self.figure.add_subplot(111)
            self.note_artist = None
            super().__init__(self.figure)
            self.setParent(parent)
            self.title = title
            self.x_label = x_label
            self.y_label = y_label
            self.reset()
        def reset(self) -> None:
            self.ax.clear()
            self.note_artist = None
            self.ax.set_title(self.title)
            self.ax.set_xlabel(self.x_label)
            self.ax.set_ylabel(self.y_label)
            self.ax.grid(True, alpha=0.3)
            self.draw()
    class MouseWheelBlocker:
        """阻止鼠标滚轮事件以防止意外调整数值"""
        def __init__(self, widget):
            self.widget = widget
            widget.wheelEvent = self.wheelEvent
        def wheelEvent(self, event):
            event.ignore()
    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("DCR / PDE / APP Plotter")
            self.resize(1280, 760)
            self.groups: Dict[str, List[Path]] = {}
            self.group_corrections: Dict[str, float] = {}
            self.note_configs: Dict[str, NoteConfig] = {"dcr": NoteConfig(), "app": NoteConfig()}
            self._drag_key: Optional[str] = None
            self._drag_dx = 0.0
            self._drag_dy = 0.0
            self._build_ui()
            self._add_group(default_name="Group A")
        def _build_ui(self) -> None:
            root = QWidget()
            root_layout = QVBoxLayout(root)
            splitter = QSplitter(Qt.Horizontal)
            left = QWidget()
            left.setMinimumWidth(380)
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(8, 8, 8, 8)
            left_layout.setSpacing(10)
            group_box = QGroupBox("Data Groups")
            group_layout = QVBoxLayout(group_box)
            self.group_list = QListWidget()
            self.group_list.currentItemChanged.connect(self._refresh_file_view)
            self.group_list.currentItemChanged.connect(self._on_group_selection_changed)
            group_layout.addWidget(self.group_list)
            form = QFormLayout()
            self.group_name_edit = QLineEdit()
            form.addRow("Group Name", self.group_name_edit)
            group_layout.addLayout(form)
            btns = QGridLayout()
            self.btn_add_group = QPushButton("New Group")
            self.btn_rename_group = QPushButton("Rename Group")
            self.btn_delete_group = QPushButton("Delete Group")
            self.btn_add_files = QPushButton("Add CSV Files")
            self.btn_auto_group_files = QPushButton("Auto Group by Prefix")
            self.btn_remove_files = QPushButton("Clear Group Files")
            self.btn_add_group.clicked.connect(self._on_add_group)
            self.btn_rename_group.clicked.connect(self._on_rename_group)
            self.btn_delete_group.clicked.connect(self._on_delete_group)
            self.btn_add_files.clicked.connect(self._on_add_files)
            self.btn_auto_group_files.clicked.connect(self._on_auto_group_files)
            self.btn_remove_files.clicked.connect(self._on_clear_group_files)
            btns.addWidget(self.btn_add_group, 0, 0)
            btns.addWidget(self.btn_rename_group, 0, 1)
            btns.addWidget(self.btn_delete_group, 1, 0)
            btns.addWidget(self.btn_add_files, 1, 1)
            btns.addWidget(self.btn_auto_group_files, 2, 0, 1, 2)
            btns.addWidget(self.btn_remove_files, 3, 0, 1, 2)
            group_layout.addLayout(btns)
            auto_opts = QHBoxLayout()
            self.auto_use_temp = QCheckBox("Temp")
            self.auto_use_temp.setChecked(True)
            self.auto_use_gate = QCheckBox("Gate")
            self.auto_use_gate.setChecked(True)
            auto_opts.addWidget(QLabel("Auto Group Params:"))
            auto_opts.addWidget(self.auto_use_temp)
            auto_opts.addWidget(self.auto_use_gate)
            auto_opts.addStretch(1)
            group_layout.addLayout(auto_opts)
            left_layout.addWidget(group_box)
            files_box = QGroupBox("Selected Group Files")
            files_layout = QVBoxLayout(files_box)
            self.files_view = QTextEdit()
            self.files_view.setReadOnly(True)
            files_layout.addWidget(self.files_view)
            left_layout.addWidget(files_box)
            control_box = QGroupBox("Plot / Export")
            control_layout = QVBoxLayout(control_box)
            suffix_form = QFormLayout()
            self.suffix_edit = QLineEdit("run1")
            suffix_form.addRow("File Suffix", self.suffix_edit)
            control_layout.addLayout(suffix_form)
            style_form = QFormLayout()
            self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(6, 48); self.font_size_spin.setValue(11)
            self.line_width_spin = QDoubleSpinBox(); self.line_width_spin.setRange(0.5, 10.0); self.line_width_spin.setSingleStep(0.1); self.line_width_spin.setDecimals(2); self.line_width_spin.setValue(1.5)
            self.fig_width_spin = QDoubleSpinBox(); self.fig_width_spin.setRange(0.5, 30.0); self.fig_width_spin.setSingleStep(0.25); self.fig_width_spin.setDecimals(2); self.fig_width_spin.setValue(8.0)
            self.fig_height_spin = QDoubleSpinBox(); self.fig_height_spin.setRange(0.5, 30.0); self.fig_height_spin.setSingleStep(0.25); self.fig_height_spin.setDecimals(2); self.fig_height_spin.setValue(5.0)
            self.legend_loc_combo = QComboBox(); self.legend_loc_combo.addItem("Upper Right", "upper right"); self.legend_loc_combo.addItem("Upper Left", "upper left"); self.legend_loc_combo.addItem("Lower Right", "lower right"); self.legend_loc_combo.addItem("Lower Left", "lower left")
            self.export_dpi_combo = QComboBox(); self.export_dpi_combo.addItem("72 DPI (Web)", 72); self.export_dpi_combo.addItem("150 DPI (Draft)", 150); self.export_dpi_combo.addItem("300 DPI (High)", 300); self.export_dpi_combo.addItem("600 DPI (Print)", 600); self.export_dpi_combo.addItem("1200 DPI (Ultra)", 1200); self.export_dpi_combo.setCurrentIndex(2)
            self.export_format_combo = QComboBox(); self.export_format_combo.addItem("TIFF + LZW (Lossless)", "tiff"); self.export_format_combo.addItem("PNG (Lossless)", "png"); self.export_format_combo.addItem("JPEG (Lossy, Smallest)", "jpeg")
            self.pde_correction_mode_combo = QComboBox(); self.pde_correction_mode_combo.addItem("Global", "global"); self.pde_correction_mode_combo.addItem("Per Group", "per_group")
            self.pde_correction_factor_spin = QDoubleSpinBox(); self.pde_correction_factor_spin.setRange(0.01, 100.0); self.pde_correction_factor_spin.setSingleStep(0.01); self.pde_correction_factor_spin.setDecimals(4); self.pde_correction_factor_spin.setValue(1.0)
            self.group_correction_factor_spin = QDoubleSpinBox(); self.group_correction_factor_spin.setRange(0.01, 100.0); self.group_correction_factor_spin.setSingleStep(0.01); self.group_correction_factor_spin.setDecimals(4); self.group_correction_factor_spin.setValue(1.0)
            self.note_enabled_check = QCheckBox("Enable Note"); self.note_enabled_check.setChecked(True)
            self.note_text_edit = QLineEdit("Custom Note")
            self.note_loc_combo = QComboBox(); self.note_loc_combo.addItem("Upper Left", "upper left"); self.note_loc_combo.addItem("Upper Right", "upper right"); self.note_loc_combo.addItem("Lower Left", "lower left"); self.note_loc_combo.addItem("Lower Right", "lower right"); self.note_loc_combo.addItem("Center", "center")
            self.note_font_spin = QSpinBox(); self.note_font_spin.setRange(6, 48); self.note_font_spin.setValue(11)
            self.btn_reset_note = QPushButton("Reset Note Position")
            style_form.addRow("Font Size", self.font_size_spin)
            style_form.addRow("Line Width", self.line_width_spin)
            style_form.addRow("Figure Width (in)", self.fig_width_spin)
            style_form.addRow("Figure Height (in)", self.fig_height_spin)
            style_form.addRow("Legend Position", self.legend_loc_combo)
            style_form.addRow("Export DPI", self.export_dpi_combo)
            style_form.addRow("Export Format", self.export_format_combo)
            style_form.addRow("PDE Correction Mode", self.pde_correction_mode_combo)
            style_form.addRow("PDE Correction Factor", self.pde_correction_factor_spin)
            style_form.addRow("Group PDE Factor", self.group_correction_factor_spin)
            style_form.addRow("Note Enabled", self.note_enabled_check)
            style_form.addRow("Note Text", self.note_text_edit)
            style_form.addRow("Note Position", self.note_loc_combo)
            style_form.addRow("Note Font Size", self.note_font_spin)
            style_form.addRow("", self.btn_reset_note)
            control_layout.addLayout(style_form)
            # 禁用所有数值输入框和下拉菜单的鼠标滚轮调整
            for widget in [self.font_size_spin, self.line_width_spin, self.fig_width_spin, 
                          self.fig_height_spin, self.legend_loc_combo, self.export_dpi_combo,
                          self.export_format_combo, self.pde_correction_factor_spin, 
                          self.pde_correction_mode_combo, self.group_correction_factor_spin,
                          self.note_font_spin, self.note_loc_combo]:
                MouseWheelBlocker(widget)
            self.btn_apply_style = QPushButton("Apply Style")
            self.btn_apply_style.clicked.connect(self._apply_style_to_canvases)
            control_layout.addWidget(self.btn_apply_style)
            self.note_enabled_check.toggled.connect(self._apply_note_settings_to_canvases)
            self.note_text_edit.editingFinished.connect(self._apply_note_settings_to_canvases)
            self.note_loc_combo.currentIndexChanged.connect(self._on_note_loc_changed)
            self.note_font_spin.valueChanged.connect(self._apply_note_settings_to_canvases)
            self.btn_reset_note.clicked.connect(self._reset_note_positions)
            self.pde_correction_mode_combo.currentIndexChanged.connect(self._on_pde_correction_mode_changed)
            self.group_correction_factor_spin.valueChanged.connect(self._on_group_factor_changed)
            self.btn_plot = QPushButton("Parse + Plot")
            self.btn_save_dcr = QPushButton("Save PDE-DCR TIFF")
            self.btn_save_app = QPushButton("Save PDE-APP TIFF")
            self.btn_save_both = QPushButton("Save Both TIFF")
            self.btn_copy_dcr = QPushButton("Copy PDE-DCR Image")
            self.btn_copy_app = QPushButton("Copy PDE-APP Image")
            self.btn_plot.clicked.connect(self._plot_all)
            self.btn_save_dcr.clicked.connect(lambda: self._save_plot(self.canvas_dcr, "PDE-DCR"))
            self.btn_save_app.clicked.connect(lambda: self._save_plot(self.canvas_app, "PDE-APP"))
            self.btn_save_both.clicked.connect(self._save_both)
            self.btn_copy_dcr.clicked.connect(lambda: self._copy_plot_to_clipboard(self.canvas_dcr))
            self.btn_copy_app.clicked.connect(lambda: self._copy_plot_to_clipboard(self.canvas_app))
            control_layout.addWidget(self.btn_plot)
            control_layout.addWidget(self.btn_save_dcr)
            control_layout.addWidget(self.btn_save_app)
            control_layout.addWidget(self.btn_save_both)
            control_layout.addWidget(self.btn_copy_dcr)
            control_layout.addWidget(self.btn_copy_app)
            left_layout.addWidget(control_box)
            right = QWidget()
            right_layout = QVBoxLayout(right)
            tabs = QTabWidget()
            self.canvas_dcr = MatplotlibCanvas("PDE vs DCR", "PDE (%)", "DCR (k)")
            self.canvas_app = MatplotlibCanvas("PDE vs APP", "PDE (%)", "APP (%)")
            self._bind_note_drag_handlers(self.canvas_dcr, "dcr")
            self._bind_note_drag_handlers(self.canvas_app, "app")
            tab1 = QWidget(); t1 = QVBoxLayout(tab1); t1.addWidget(self.canvas_dcr)
            tab2 = QWidget(); t2 = QVBoxLayout(tab2); t2.addWidget(self.canvas_app)
            tabs.addTab(tab1, "PDE vs DCR")
            tabs.addTab(tab2, "PDE vs APP")
            right_layout.addWidget(tabs)
            left_scroll = QScrollArea()
            left_scroll.setWidgetResizable(True)
            left_scroll.setFrameShape(QScrollArea.NoFrame)
            left_scroll.setWidget(left)

            splitter.addWidget(left_scroll)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([420, 860])
            root_layout.addWidget(splitter)
            self.setCentralWidget(root)
            self._apply_style_to_canvases()
            self._apply_note_settings_to_canvases()
        def _selected_group_name(self) -> Optional[str]:
            item = self.group_list.currentItem()
            return item.text() if item else None
        def _add_group(self, default_name: Optional[str] = None) -> None:
            name = default_name or (self.group_name_edit.text().strip() or "Group")
            if default_name is None:
                base = name; idx = 1
                while name in self.groups:
                    idx += 1; name = f"{base} {idx}"
            if name in self.groups:
                QMessageBox.warning(self, "Duplicate Group", f"Group '{name}' already exists."); return
            self.groups[name] = []
            self.group_corrections.setdefault(name, 1.0)
            self.group_list.addItem(QListWidgetItem(name))
            self.group_list.setCurrentRow(self.group_list.count() - 1)
        def _on_add_group(self) -> None:
            self._add_group()
        def _on_rename_group(self) -> None:
            old = self._selected_group_name()
            if not old:
                QMessageBox.information(self, "No Selection", "Please select a group first."); return
            new = self.group_name_edit.text().strip()
            if not new:
                QMessageBox.warning(self, "Invalid Name", "Group name cannot be empty."); return
            if new != old and new in self.groups:
                QMessageBox.warning(self, "Duplicate Group", f"Group '{new}' already exists."); return
            self.groups[new] = self.groups.pop(old)
            if old in self.group_corrections:
                self.group_corrections[new] = self.group_corrections.pop(old)
            self.group_list.currentItem().setText(new)
        def _on_delete_group(self) -> None:
            name = self._selected_group_name()
            if not name:
                QMessageBox.information(self, "No Selection", "Please select a group first."); return
            self.groups.pop(name, None)
            self.group_corrections.pop(name, None)
            self.group_list.takeItem(self.group_list.currentRow())
            self._refresh_file_view()
        def _on_add_files(self) -> None:
            name = self._selected_group_name()
            if not name:
                QMessageBox.information(self, "No Selection", "Please select a group first."); return
            files, _ = QFileDialog.getOpenFileNames(self, "Select CSV Files", "", "CSV Files (*.csv);;All Files (*.*)")
            if not files:
                return
            existing = {p.resolve() for p in self.groups[name]}
            for f in files:
                p = Path(f)
                rp = p.resolve()
                if rp not in existing:
                    self.groups[name].append(p)
                    existing.add(rp)
            self._refresh_file_view(); self._plot_all()
        @staticmethod
        def _format_numeric_text(value: float) -> str:
            return ("{:.6f}".format(value)).rstrip("0").rstrip(".")
        @staticmethod
        def _extract_prefix_token(file_path: Path) -> str:
            stem = file_path.stem.strip()
            if not stem:
                return "Group"
            prefix = re.split(r"[-_]", stem, maxsplit=1)[0].strip()
            if not prefix:
                return "Group"
            up = prefix.upper()
            return up[0] if up and up[0] in {"A", "B", "C"} else up
        def _build_auto_group_name(self, file_path: Path) -> Tuple[Optional[str], Optional[str]]:
            text = file_path.stem
            prefix = self._extract_prefix_token(file_path)
            temp_m = TEMP_PATTERN.search(text)
            gate_m = GATE_PATTERN.search(text)
            parts: List[str] = [prefix]
            if self.auto_use_temp.isChecked():
                if not temp_m: return None, f"missing Temp in filename: {file_path.name}"
                parts.append(f"Temp{self._format_numeric_text(float(temp_m.group('temp')))}")
            if self.auto_use_gate.isChecked():
                if not gate_m: return None, f"missing Gate in filename: {file_path.name}"
                parts.append(f"Gate{self._format_numeric_text(float(gate_m.group('gate')))}")
            return "-".join(parts), None
        def _ensure_group_exists(self, group_name: str) -> None:
            if group_name in self.groups:
                return
            self.groups[group_name] = []
            self.group_corrections.setdefault(group_name, 1.0)
            self.group_list.addItem(QListWidgetItem(group_name))
        def _all_group_files(self) -> set[Path]:
            result: set[Path] = set()
            for files in self.groups.values():
                for f in files:
                    try:
                        result.add(f.resolve())
                    except Exception:
                        pass
            return result
        def _on_auto_group_files(self) -> None:
            if not self.auto_use_temp.isChecked() and not self.auto_use_gate.isChecked():
                QMessageBox.warning(self, "Invalid Auto Group Params", "Please check Temp and/or Gate."); return
            files, _ = QFileDialog.getOpenFileNames(self, "Select CSV Files For Auto Group", "", "CSV Files (*.csv);;All Files (*.*)")
            if not files:
                return
            existing = self._all_group_files(); errors: List[str] = []; added = 0
            for f in files:
                p = Path(f); rp = p.resolve()
                if rp in existing:
                    continue
                group_name, err = self._build_auto_group_name(p)
                if err:
                    errors.append(err); continue
                if not group_name:
                    errors.append(f"failed to build group: {p.name}"); continue
                self._ensure_group_exists(group_name)
                self.groups[group_name].append(p)
                existing.add(rp); added += 1
            if self.group_list.count() > 0 and self.group_list.currentRow() < 0:
                self.group_list.setCurrentRow(0)
            self._refresh_file_view(); self._plot_all()
            if errors:
                QMessageBox.warning(self, "Auto Group Partial Failure", "Some files were not auto-grouped:\n" + "\n".join(errors[:20]))
            else:
                QMessageBox.information(self, "Auto Group Done", f"Added {added} file(s).")
        def _on_clear_group_files(self) -> None:
            name = self._selected_group_name()
            if not name:
                QMessageBox.information(self, "No Selection", "Please select a group first."); return
            self.groups[name] = []
            self._refresh_file_view(); self._plot_all()
        def _refresh_file_view(self, *_args) -> None:
            name = self._selected_group_name()
            if not name:
                self.files_view.clear()
                return
            files = self.groups.get(name, [])
            self.files_view.setPlainText("No files in this group." if not files else "\n".join(str(f) for f in files))
        def _collect_group_points(self) -> Tuple[Dict[str, List[DataPoint]], List[str]]:
            group_points: Dict[str, List[DataPoint]] = {}
            errors: List[str] = []
            for group_name, files in self.groups.items():
                points: List[DataPoint] = []
                for file_path in files:
                    parsed = parse_file_to_point(file_path)
                    if parsed is None:
                        errors.append(f"[{group_name}] parse failed: {file_path}")
                        continue
                    points.append(parsed)
                points.sort(key=lambda p: p.pde_percent)
                if points:
                    group_points[group_name] = points
            return group_points, errors
        def _current_plot_style(self) -> dict[str, float]:
            return {"font_size": float(self.font_size_spin.value()), "line_width": float(self.line_width_spin.value()), "fig_width": float(self.fig_width_spin.value()), "fig_height": float(self.fig_height_spin.value())}
        def _current_legend_loc(self) -> str:
            return str(self.legend_loc_combo.currentData() or "upper right")
        def _current_export_dpi(self) -> int:
            return int(self.export_dpi_combo.currentData())
        def _current_export_format(self) -> str:
            return str(self.export_format_combo.currentData())
        def _current_pde_correction_mode(self) -> str:
            return str(self.pde_correction_mode_combo.currentData() or "global")
        def _get_pde_correction_factor(self) -> float:
            return float(self.pde_correction_factor_spin.value())
        def _get_group_correction_factor(self, group_name: str) -> float:
            return float(self.group_corrections.get(group_name, 1.0))
        def _on_group_selection_changed(self, *_args) -> None:
            name = self._selected_group_name()
            if not name:
                return
            factor = self.group_corrections.get(name, 1.0)
            self.group_correction_factor_spin.blockSignals(True)
            self.group_correction_factor_spin.setValue(factor)
            self.group_correction_factor_spin.blockSignals(False)
        def _on_group_factor_changed(self, value: float) -> None:
            name = self._selected_group_name()
            if not name:
                return
            self.group_corrections[name] = float(value)
            self._plot_all()
        @staticmethod
        def _clamp01(value: float) -> float:
            return max(0.0, min(1.0, value))
        @staticmethod
        def _note_defaults_for_loc(loc: str) -> tuple[float, float, str, str]:
            mapping = {
                "upper left": (0.03, 0.97, "left", "top"),
                "upper right": (0.97, 0.97, "right", "top"),
                "lower left": (0.03, 0.03, "left", "bottom"),
                "lower right": (0.97, 0.03, "right", "bottom"),
                "center": (0.50, 0.50, "center", "center"),
            }
            return mapping.get(loc, mapping["upper left"])
        def _sync_note_configs_from_ui(self, reset_positions: bool = False) -> None:
            enabled = self.note_enabled_check.isChecked()
            text = self.note_text_edit.text().strip()
            loc = str(self.note_loc_combo.currentData() or "upper left")
            fontsize = int(self.note_font_spin.value())
            for cfg in self.note_configs.values():
                cfg.enabled = enabled
                cfg.text = text
                cfg.loc = loc
                cfg.fontsize = fontsize
                if reset_positions:
                    cfg.x, cfg.y, cfg.ha, cfg.va = self._note_defaults_for_loc(loc)
        def _render_note_on_canvas(self, canvas: MatplotlibCanvas, cfg: NoteConfig) -> None:
            if canvas.note_artist is not None:
                try:
                    canvas.note_artist.remove()
                except Exception:
                    pass
                canvas.note_artist = None
            if not cfg.enabled or not cfg.text:
                return
            artist = canvas.ax.text(
                cfg.x,
                cfg.y,
                cfg.text,
                transform=canvas.ax.transAxes,
                fontsize=cfg.fontsize,
                color="black",
                ha=cfg.ha,
                va=cfg.va,
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": "white",
                    "edgecolor": "black",
                    "alpha": 0.65,
                },
                zorder=10,
            )
            canvas.note_artist = artist
        def _render_notes(self) -> None:
            self._render_note_on_canvas(self.canvas_dcr, self.note_configs["dcr"])
            self._render_note_on_canvas(self.canvas_app, self.note_configs["app"])
        def _apply_note_settings_to_canvases(self, reset_positions: bool = False) -> None:
            if not hasattr(self, "canvas_dcr") or not hasattr(self, "canvas_app"):
                return
            self._sync_note_configs_from_ui(reset_positions=reset_positions)
            self._render_notes()
            self.canvas_dcr.draw()
            self.canvas_app.draw()
        def _reset_note_positions(self) -> None:
            self._apply_note_settings_to_canvases(reset_positions=True)
        def _on_note_loc_changed(self, *_args) -> None:
            self._apply_note_settings_to_canvases(reset_positions=True)
        def _bind_note_drag_handlers(self, canvas: MatplotlibCanvas, canvas_key: str) -> None:
            canvas.mpl_connect("button_press_event", lambda event: self._on_note_press(canvas_key, canvas, event))
            canvas.mpl_connect("motion_notify_event", lambda event: self._on_note_motion(canvas_key, canvas, event))
            canvas.mpl_connect("button_release_event", lambda event: self._on_note_release(canvas_key, canvas, event))
        def _on_note_press(self, canvas_key: str, canvas: MatplotlibCanvas, event) -> None:
            if event.button != 1 or event.inaxes != canvas.ax:
                return
            cfg = self.note_configs.get(canvas_key)
            artist = getattr(canvas, "note_artist", None)
            if cfg is None or artist is None:
                return
            contains, _ = artist.contains(event)
            if not contains:
                return
            x_axes, y_axes = canvas.ax.transAxes.inverted().transform((event.x, event.y))
            self._drag_key = canvas_key
            self._drag_dx = cfg.x - x_axes
            self._drag_dy = cfg.y - y_axes
        def _on_note_motion(self, canvas_key: str, canvas: MatplotlibCanvas, event) -> None:
            if self._drag_key != canvas_key or event.inaxes != canvas.ax or event.x is None or event.y is None:
                return
            cfg = self.note_configs.get(canvas_key)
            artist = getattr(canvas, "note_artist", None)
            if cfg is None or artist is None:
                return
            x_axes, y_axes = canvas.ax.transAxes.inverted().transform((event.x, event.y))
            cfg.x = self._clamp01(x_axes + self._drag_dx)
            cfg.y = self._clamp01(y_axes + self._drag_dy)
            artist.set_position((cfg.x, cfg.y))
            canvas.draw_idle()
        def _on_note_release(self, canvas_key: str, canvas: MatplotlibCanvas, event) -> None:
            if self._drag_key == canvas_key:
                self._drag_key = None
        def _on_pde_correction_mode_changed(self, *_args) -> None:
            self._plot_all()
        def _pde_factor_for_group(self, group_name: str) -> float:
            mode = self._current_pde_correction_mode()
            if mode == "per_group":
                return self._get_group_correction_factor(group_name)
            return self._get_pde_correction_factor()
        def _apply_style_to_canvases(self) -> None:
            style = self._current_plot_style()
            self._sync_note_configs_from_ui(reset_positions=False)
            for canvas in (self.canvas_dcr, self.canvas_app):
                canvas.figure.set_size_inches(style["fig_width"], style["fig_height"], forward=True)
                canvas.ax.tick_params(axis="both", labelsize=style["font_size"])
                canvas.ax.title.set_fontsize(style["font_size"] + 2.0)
                canvas.ax.xaxis.label.set_fontsize(style["font_size"])
                canvas.ax.yaxis.label.set_fontsize(style["font_size"])
                for spine in canvas.ax.spines.values():
                    spine.set_linewidth(style["line_width"])
                legend = canvas.ax.get_legend()
                if legend is not None:
                    for text in legend.get_texts():
                        text.set_fontsize(style["font_size"])
            self._render_notes(); self.canvas_dcr.draw(); self.canvas_app.draw()
        def _plot_all(self) -> None:
            group_points, errors = self._collect_group_points()
            style = self._current_plot_style()
            self._sync_note_configs_from_ui(reset_positions=False)
            self.canvas_dcr.reset(); self.canvas_app.reset()
            for canvas in (self.canvas_dcr, self.canvas_app):
                canvas.figure.set_size_inches(style["fig_width"], style["fig_height"], forward=True)
                canvas.ax.tick_params(axis="both", labelsize=style["font_size"])
                canvas.ax.title.set_fontsize(style["font_size"] + 2.0)
                canvas.ax.xaxis.label.set_fontsize(style["font_size"])
                canvas.ax.yaxis.label.set_fontsize(style["font_size"])
            for group_name, points in group_points.items():
                points = sorted(points, key=lambda p: p.pde_percent)
                pde_factor = self._pde_factor_for_group(group_name)
                pde = [p.pde_percent * pde_factor for p in points]
                dcr = [p.dcr_k for p in points]
                app = [p.app_percent for p in points]
                self.canvas_dcr.ax.plot(pde, dcr, marker="o", linewidth=style["line_width"], label=group_name)
                self.canvas_app.ax.plot(pde, app, marker="o", linewidth=style["line_width"], label=group_name)
            if group_points:
                self.canvas_dcr.ax.legend(loc=self._current_legend_loc(), fontsize=style["font_size"])
                self.canvas_app.ax.legend(loc=self._current_legend_loc(), fontsize=style["font_size"])
            self._render_notes(); self.canvas_dcr.draw(); self.canvas_app.draw()
            if errors:
                QMessageBox.warning(self, "Partial Parse Failure", "Some files could not be parsed:\n" + "\n".join(errors[:20]))
        def _build_save_name(self, prefix: str) -> str:
            suffix = self.suffix_edit.text().strip()
            ext = self._current_export_format()
            base_name = f"{prefix}-{suffix}" if suffix else prefix
            return f"{base_name}.{ext}"
        def _copy_plot_to_clipboard(self, canvas: MatplotlibCanvas) -> None:
            buffer = BytesIO()
            canvas.figure.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
            qimg = QImage.fromData(buffer.getvalue(), "PNG")
            if qimg.isNull():
                QMessageBox.warning(self, "Copy Failed", "Failed to copy image to clipboard.")
                return
            QApplication.clipboard().setImage(qimg)
            QMessageBox.information(self, "Copied", "Plot image copied to clipboard.")
        def _save_plot(self, canvas: MatplotlibCanvas, prefix: str) -> None:
            self._apply_style_to_canvases()
            default_name = self._build_save_name(prefix)
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Image", default_name, "All Files (*.*)")
            if not save_path:
                return
            fmt = self._current_export_format()
            dpi = self._current_export_dpi()
            if fmt == "tiff":
                canvas.figure.savefig(save_path, dpi=dpi, format="tiff", bbox_inches="tight", pil_kwargs={"compression": "lzw"})
            elif fmt == "png":
                canvas.figure.savefig(save_path, dpi=dpi, format="png", bbox_inches="tight")
            elif fmt == "jpeg":
                canvas.figure.savefig(save_path, dpi=dpi, format="jpeg", bbox_inches="tight", pil_kwargs={"quality": 95, "optimize": True})
            QMessageBox.information(self, "Saved", f"Saved to:\n{save_path}")
        def _save_both(self) -> None:
            self._apply_style_to_canvases()
            folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
            if not folder:
                return
            fmt = self._current_export_format()
            dpi = self._current_export_dpi()
            folder_path = Path(folder)
            dcr_path = folder_path / self._build_save_name("PDE-DCR")
            app_path = folder_path / self._build_save_name("PDE-APP")
            save_kwargs: dict[str, object] = {"dpi": dpi, "bbox_inches": "tight"}
            if fmt == "tiff":
                save_kwargs["format"] = "tiff"
                save_kwargs["pil_kwargs"] = {"compression": "lzw"}
            elif fmt == "png":
                save_kwargs["format"] = "png"
            elif fmt == "jpeg":
                save_kwargs["format"] = "jpeg"
                save_kwargs["pil_kwargs"] = {"quality": 95, "optimize": True}
            self.canvas_dcr.figure.savefig(str(dcr_path), **save_kwargs)
            self.canvas_app.figure.savefig(str(app_path), **save_kwargs)
            QMessageBox.information(self, "Saved", f"Saved files:\n{dcr_path}\n{app_path}")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
def main() -> int:
    parser = argparse.ArgumentParser(description="DCR/PDE/APP CSV plotter")
    parser.add_argument("--self-test", action="store_true", help="Run parser self-test and exit")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    return launch_gui()
if __name__ == "__main__":
    sys.exit(main())
