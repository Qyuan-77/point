"""目标颜色自动点击器 - 图形界面入口。

运行：
    python main.py
"""

import sys

import cv2
import numpy as np
from PyQt6.QtCore import QRect, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pynput import keyboard

from capture import ScreenCapture, set_dpi_awareness
from config import Config
from detector import Detector
from worker import ClickWorker


class RegionSelector(QWidget):
    """全屏半透明遮罩，按住鼠标拖出检测区域。"""

    region_selected = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        self._start = None
        self._current = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.virtualGeometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._scale = self.devicePixelRatioF()

    # ---- 鼠标 ----
    def mousePressEvent(self, event):
        self._start = event.position().toPoint()
        self._current = self._start
        self.update()

    def mouseMoveEvent(self, event):
        self._current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        start = self._start
        self._current = event.position().toPoint()
        self.close()
        if start is None:
            return
        rect = self._normalized_rect(start, self._current)
        if rect.width() >= 5 and rect.height() >= 5:
            self.region_selected.emit(
                (
                    int(rect.x() * self._scale),
                    int(rect.y() * self._scale),
                    int(rect.width() * self._scale),
                    int(rect.height() * self._scale),
                )
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # ---- 绘制 ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self._start is not None and self._current is not None:
            rect = self._normalized_rect(self._start, self._current)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(rect)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.drawText(rect.x() + 4, rect.y() + 20, f"{rect.width()} × {rect.height()}")
        painter.end()

    @staticmethod
    def _normalized_rect(a, b):
        return QRect(
            min(a.x(), b.x()),
            min(a.y(), b.y()),
            abs(a.x() - b.x()),
            abs(a.y() - b.y()),
        )


class HotkeyThread(QThread):
    """Global hotkey listener (pynput), running in a background thread."""

    triggered = pyqtSignal(str)

    def __init__(self, hotkeys, parent=None):
        super().__init__(parent)
        self._hotkeys = dict(hotkeys)  # e.g. {"<f8>": "stop"}
        self._listener = None

    def run(self):
        try:
            listener = keyboard.GlobalHotKeys(
                {
                    key: (lambda name=name: self.triggered.emit(name))
                    for key, name in self._hotkeys.items()
                }
            )
            self._listener = listener
            listener.start()
            listener.join()
        except Exception as exc:
            self.triggered.emit(f"hotkey_error:{exc}")

    def stop(self):
        for _ in range(100):
            if self._listener is not None:
                break
            QThread.msleep(20)
        listener = self._listener
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._region_selector = None
        self._capture = ScreenCapture()
        self._detector = Detector()
        self._hotkey_thread = None
        self.setWindowTitle("目标颜色自动点击器")
        self.resize(780, 860)
        self._build_ui()
        self._start_hotkeys()
        self._append_log("提示：先设置检测区域，再点“预览”确认识别结果，最后点“开始”。")
        b = self._capture.screen_bounds
        self._append_log(f"屏幕范围：left={b[0]}, top={b[1]}, w={b[2]}, h={b[3]}")

    # ---------------- 界面 ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # 检测区域
        region_box = QGroupBox("检测区域（物理像素）")
        region_layout = QGridLayout(region_box)
        self.spin_x = self._spin(0, 20000, 0)
        self.spin_y = self._spin(0, 20000, 0)
        self.spin_w = self._spin(1, 20000, 800)
        self.spin_h = self._spin(1, 20000, 600)
        for col, (label, spin) in enumerate(
            [("X", self.spin_x), ("Y", self.spin_y), ("宽", self.spin_w), ("高", self.spin_h)]
        ):
            region_layout.addWidget(QLabel(label), 0, col * 2)
            region_layout.addWidget(spin, 0, col * 2 + 1)
        self.btn_pick = QPushButton("框选区域")
        self.btn_pick.clicked.connect(self.pick_region)
        region_layout.addWidget(self.btn_pick, 0, 8, 1, 2)
        root.addWidget(region_box)

        # 检测参数
        detect_box = QGroupBox("检测参数")
        detect_layout = QFormLayout(detect_box)

        self.threshold = QSlider(Qt.Orientation.Horizontal)
        self.threshold.setRange(0, 255)
        self.threshold.setValue(180)
        self.lbl_threshold = QLabel("180")
        self.threshold.valueChanged.connect(lambda v: self.lbl_threshold.setText(str(v)))
        thr_row = QHBoxLayout()
        thr_row.addWidget(self.threshold, 1)
        thr_row.addWidget(self.lbl_threshold)
        detect_layout.addRow("灰度阈值", thr_row)

        self.chk_invert = QCheckBox("检测暗色目标（反相）")
        self.chk_otsu = QCheckBox("OTSU 自动阈值")
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.chk_invert)
        mode_row.addWidget(self.chk_otsu)
        detect_layout.addRow("模式", mode_row)

        self.spin_min_area = self._spin(1, 100000, 50)
        detect_layout.addRow("最小目标面积", self.spin_min_area)

        self.spin_dup = self._spin(0, 200, 15)
        detect_layout.addRow("去重半径(px)", self.spin_dup)

        self.combo_order = QComboBox()
        self.combo_order.addItem("从上到下、从左到右", "y_x")
        self.combo_order.addItem("从左到右、从上到下", "x_y")
        self.combo_order.addItem("距左上角由近到远", "corner")
        detect_layout.addRow("点击顺序", self.combo_order)

        self.chk_grid = QCheckBox("区域内生成等距点阵（多点模式）")
        self.chk_grid.setChecked(True)
        detect_layout.addRow("多点模式", self.chk_grid)

        self.spin_grid = self._spin(3, 200, 20)
        detect_layout.addRow("点阵间距(px)", self.spin_grid)

        self.spin_max_points = self._spin(10, 5000, 800)
        detect_layout.addRow("单帧最多点数", self.spin_max_points)

        self.chk_dist_center = QCheckBox("用距离变换取目标中心（避免点到边缘）")
        self.chk_dist_center.setChecked(True)
        detect_layout.addRow("中心方式", self.chk_dist_center)
        root.addWidget(detect_box)

        # 点击与验证
        click_box = QGroupBox("点击与验证")
        click_layout = QFormLayout(click_box)

        self.spin_interval = self._dspin(0.05, 2.0, 0.15)
        click_layout.addRow("点击间隔(s)", self.spin_interval)

        self.spin_verify = self._dspin(0.05, 2.0, 0.25)
        click_layout.addRow("验证等待(s)", self.spin_verify)

        self.spin_retries = self._spin(0, 10, 3)
        click_layout.addRow("最大重试次数", self.spin_retries)

        self.spin_red_px = self._spin(1, 2000, 12)
        click_layout.addRow("成功所需红像素", self.spin_red_px)

        self.spin_red_ratio = self._spin(1, 90, 15)
        click_layout.addRow("红区排除占比(%)", self.spin_red_ratio)

        self.chk_autostop = QCheckBox("全部完成后自动停止")
        self.chk_autostop.setChecked(True)
        click_layout.addRow("停止方式", self.chk_autostop)
        root.addWidget(click_box)

        # 预览与日志
        self.preview = QLabel("预览区")
        self.preview.setMinimumHeight(240)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#202020; color:#ccc;")
        root.addWidget(self.preview, 1)

        self.lbl_stats = QLabel("剩余目标：-    已点击：0    失败：0")
        root.addWidget(self.lbl_stats)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        root.addWidget(self.log_view)

        btn_row = QHBoxLayout()
        self.btn_preview = QPushButton("预览（只识别不点击）")
        self.btn_calibrate = QPushButton("自动校准")
        self.btn_start = QPushButton("开始")
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_calibrate)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        root.addLayout(btn_row)

        self.btn_preview.clicked.connect(self.preview_once)
        self.btn_calibrate.clicked.connect(self.calibrate_region)
        self.btn_start.clicked.connect(self.start_click)
        self.btn_stop.clicked.connect(self.stop_click)

    @staticmethod
    def _spin(lo, hi, val):
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(val)
        return spin

    @staticmethod
    def _dspin(lo, hi, val):
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setValue(val)
        return spin

    # ---------------- 区域选择 ----------------
    def pick_region(self):
        if self._worker and self._worker.isRunning():
            self._append_log("运行中不能修改区域，请先停止。")
            return
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.show()
        self._region_selector.raise_()
        self._region_selector.activateWindow()

    def _on_region_selected(self, region):
        x, y, w, h = region
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self._append_log(f"检测区域已设置为 ({x}, {y}, {w}×{h})")

    # ---------------- 配置 ----------------
    def _make_config(self):
        return Config(
            region=(
                self.spin_x.value(),
                self.spin_y.value(),
                self.spin_w.value(),
                self.spin_h.value(),
            ),
            gray_threshold=self.threshold.value(),
            invert_bright=self.chk_invert.isChecked(),
            use_otsu=self.chk_otsu.isChecked(),
            min_area=self.spin_min_area.value(),
            duplicate_distance=self.spin_dup.value(),
            click_order=self.combo_order.currentData(),
            generate_grid=self.chk_grid.isChecked(),
            grid_spacing=self.spin_grid.value(),
            max_points=self.spin_max_points.value(),
            use_distance_center=self.chk_dist_center.isChecked(),
            click_interval=round(self.spin_interval.value(), 3),
            verify_delay=round(self.spin_verify.value(), 3),
            max_retries=self.spin_retries.value(),
            red_pixel_threshold=self.spin_red_px.value(),
            red_ratio_threshold=self.spin_red_ratio.value() / 100.0,
            auto_stop=self.chk_autostop.isChecked(),
        )

    # ---------------- 自动校准 ----------------
    def calibrate_region(self):
        if self._worker and self._worker.isRunning():
            self._append_log("运行中，请先停止再校准。")
            return
        cfg = self._make_config()
        try:
            img = self._capture.grab(cfg.region)
        except Exception as exc:
            self._append_log(f"截图失败：{exc}")
            return
        suggestions, diag = self._detector.calibrate(img)
        self.threshold.setValue(suggestions["gray_threshold"])
        self.spin_min_area.setValue(suggestions["min_area"])
        self.spin_dup.setValue(suggestions["duplicate_distance"])
        self.spin_red_px.setValue(suggestions["red_pixel_threshold"])
        self.spin_red_ratio.setValue(int(round(suggestions["red_ratio_threshold"] * 100)))
        self.chk_dist_center.setChecked(suggestions["use_distance_center"])
        self.chk_grid.setChecked(suggestions.get("generate_grid", True))
        self.spin_grid.setValue(suggestions.get("grid_spacing", self.spin_grid.value()))
        self._append_log(
            "自动校准：OTSU=%d，红点=%d 个（半径 %.1fpx，间距 %.1fpx），目标亮度 %.0f，亮块面积中位 %.0f → 参数已自动填入"
            % (
                diag["otsu"],
                diag["dots"],
                diag["med_radius"],
                diag["med_spacing"],
                diag["med_target_gray"],
                diag["med_cell_area"],
            )
        )
        if diag["dots"] == 0:
            self._append_log("提示：区域内未检测到红色圆点，红色验证参数保持默认，建议先用“预览”确认。")
        self.preview_once()

    # ---------------- 预览 ----------------
    def preview_once(self):
        if self._worker and self._worker.isRunning():
            self._append_log("运行中，请先停止再预览。")
            return
        cfg = self._make_config()
        try:
            img = self._capture.grab(cfg.region)
        except Exception as exc:
            self._append_log(f"截图失败：{exc}")
            return
        candidates, _, _ = self._detector.detect(img, cfg)
        display = img.copy()
        for i, c in enumerate(candidates, 1):
            x, y, w, h = c["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 1)
            cv2.drawMarker(
                display, (c["x"], c["y"]), (0, 0, 255), cv2.MARKER_CROSS, 16, 2
            )
            cv2.putText(
                display,
                str(i),
                (x, max(0, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
                cv2.LINE_AA,
            )
        self.show_image(display)
        text = "，".join(f"({c['x']},{c['y']})" for c in candidates[:10])
        if len(candidates) > 10:
            text += "…"
        self._append_log(f"预览：检测到 {len(candidates)} 个目标（局部坐标）：{text}")

    # ---------------- 开始/停止 ----------------
    def start_click(self):
        if self._worker and self._worker.isRunning():
            return
        cfg = self._make_config()
        x, y, w, h = cfg.region
        b = self._capture.screen_bounds
        if x < b[0] or y < b[1] or x + w > b[0] + b[2] or y + h > b[1] + b[3]:
            self._append_log("检测区域超出屏幕范围，请重新设置。")
            return
        self._worker = ClickWorker(cfg)
        self._worker.frame_ready.connect(self.show_image)
        self._worker.log.connect(self._append_log)
        self._worker.stats.connect(self._update_stats)
        self._worker.finished_ok.connect(self._on_finished)
        self._set_running(True)
        self._append_log("开始自动点击…（F8 或“停止”按钮可停止；鼠标移到屏幕左上角为紧急停止）")
        self._worker.start()

    def stop_click(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
        self._set_running(False)

    def _on_finished(self, clicked, failed):
        self._set_running(False)
        self._append_log(f"自动完成：成功 {clicked}，失败 {failed}")

    def _set_running(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_preview.setEnabled(not running)
        self.btn_calibrate.setEnabled(not running)
        self.btn_pick.setEnabled(not running)

    def _update_stats(self, remaining, clicked, failed):
        self.lbl_stats.setText(
            f"剩余目标：{remaining}    已点击：{clicked}    失败：{failed}"
        )

    # ---------------- 热键 ----------------
    def _start_hotkeys(self):
        try:
            self._hotkey_thread = HotkeyThread({"<f8>": "stop"})
            self._hotkey_thread.triggered.connect(self._on_hotkey)
            self._hotkey_thread.start()
            self._append_log("已启用全局热键：F8 = 停止（窗口不在前台也有效）")
        except Exception as exc:
            self._append_log(f"热键启动失败：{exc}")

    def _on_hotkey(self, name):
        if name.startswith("hotkey_error:"):
            self._append_log(f"热键异常：{name[len('hotkey_error:'):]}")
            return
        if name == "stop":
            if self._worker and self._worker.isRunning():
                self._append_log("F8 停止")
            self.stop_click()

    # ---------------- 通用 ----------------
    def show_image(self, img):
        if img is None or img.size == 0:
            return
        h, w, ch = img.shape
        qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview.width(),
            self.preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)

    def _append_log(self, text):
        self.log_view.append(text)

    def closeEvent(self, event):
        self.stop_click()
        if self._hotkey_thread is not None:
            self._hotkey_thread.stop()
            self._hotkey_thread.wait(2000)
        self._capture.close()
        event.accept()


def main():
    set_dpi_awareness()
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()