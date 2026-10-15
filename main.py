"""目标颜色自动点击器 - 图形界面入口。

运行：
    python main.py
"""

import sys

import cv2
from PyQt6.QtCore import QRect, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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

# 浅色卡片风：统一圆角/边框/主次按钮，替代原先的默认灰底样式。
STYLE_SHEET = """
QWidget { font-family: "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12px; color: #2b3440; }
QWidget#Root { background: #f4f6f9; }
QGroupBox {
    background: #ffffff;
    border: 1px solid #e2e7ee;
    border-radius: 8px;
    margin-top: 10px;
    padding: 8px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #5b6b7f;
}
QSpinBox, QDoubleSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #d7dee8;
    border-radius: 5px;
    padding: 2px 6px;
    min-height: 22px;
}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #3d8bfd; }
QComboBox::drop-down { border: none; width: 16px; }
QPushButton {
    background: #ffffff;
    border: 1px solid #d7dee8;
    border-radius: 6px;
    padding: 5px 12px;
    min-height: 22px;
}
QPushButton:hover { background: #eef4ff; border-color: #9dc2ff; }
QPushButton:pressed { background: #e2ecff; }
QPushButton:disabled { color: #aab4c0; background: #f2f4f7; border-color: #e6eaf0; }
QPushButton#Primary { background: #3d8bfd; border-color: #3d8bfd; color: #ffffff; font-weight: 600; }
QPushButton#Primary:hover { background: #2f7ce8; }
QPushButton#Primary:disabled { background: #b9cff0; border-color: #b9cff0; color: #ffffff; }
QPushButton#Danger { background: #ffffff; border-color: #f0b4ae; color: #c0392b; }
QPushButton#Danger:hover { background: #fdf0ee; }
QPushButton#Ghost { border: none; background: transparent; color: #3d8bfd; padding: 2px 4px; }
QCheckBox { spacing: 6px; }
QSlider::groove:horizontal { height: 4px; background: #e2e7ee; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #3d8bfd; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #3d8bfd;
    width: 12px;
    margin: -6px 0;
    border-radius: 8px;
}
QTextEdit { background: #ffffff; border: 1px solid #e2e7ee; border-radius: 8px; }
QLabel#Preview {
    background: #fbfcfe;
    border: 1px dashed #cdd7e3;
    border-radius: 8px;
    color: #8b98a8;
}
QLabel#Stats { color: #5b6b7f; }
QLabel#Hint { color: #8b98a8; font-size: 11px; }
"""


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
        self.resize(960, 680)
        self._build_ui()
        self._start_hotkeys()
        self._append_log("提示：先设置检测区域，再点“预览”确认识别结果，最后点“开始”。")
        b = self._capture.screen_bounds
        self._append_log(f"屏幕范围：left={b[0]}, top={b[1]}, w={b[2]}, h={b[3]}")

    # ---------------- 界面 ----------------
    def _build_ui(self):
        self.setObjectName("Root")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        root.addWidget(self._build_region_card())

        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_settings_column(), 0)
        body.addWidget(self._build_run_column(), 1)
        root.addLayout(body, 1)

    def _build_region_card(self):
        """顶部一行：检测区域坐标 + 框选按钮。"""
        card = self._card("检测区域（物理像素）")
        lay = QGridLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(6)
        lay.setVerticalSpacing(6)
        self.spin_x = self._spin(0, 20000, 0)
        self.spin_y = self._spin(0, 20000, 0)
        self.spin_w = self._spin(1, 20000, 800)
        self.spin_h = self._spin(1, 20000, 600)
        for col, (label, spin, tip) in enumerate(
            [
                ("X", self.spin_x, "区域左上角 X（物理像素）"),
                ("Y", self.spin_y, "区域左上角 Y（物理像素）"),
                ("宽", self.spin_w, "区域宽度（物理像素）"),
                ("高", self.spin_h, "区域高度（物理像素）"),
            ]
        ):
            lay.addWidget(QLabel(label), 0, col * 2)
            spin.setToolTip(tip)
            lay.addWidget(spin, 0, col * 2 + 1)
        self.btn_pick = QPushButton("框选区域")
        self.btn_pick.setToolTip("在全屏遮罩上按住鼠标拖出检测区域，Esc 取消")
        self.btn_pick.clicked.connect(self.pick_region)
        lay.addWidget(self.btn_pick, 0, 8, 1, 2)
        lay.setColumnStretch(7, 1)
        return card

    def _build_settings_column(self):
        """左侧参数列：检测参数 / 点击与验证 / 运行模式 / 高级参数。"""
        col = QWidget()
        col.setFixedWidth(340)
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self._build_detect_card())
        lay.addWidget(self._build_click_card())
        lay.addWidget(self._build_mode_card())
        lay.addWidget(self._build_advanced_card())
        lay.addStretch(1)
        return col

    def _build_detect_card(self):
        card = self._card("检测参数")
        lay = QGridLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(6)

        self.threshold = QSlider(Qt.Orientation.Horizontal)
        self.threshold.setRange(0, 255)
        self.threshold.setValue(180)
        self.threshold.setToolTip("灰度分割阈值：像素灰度大于该值即视为目标")
        self.lbl_threshold = QLabel("180")
        self.lbl_threshold.setMinimumWidth(26)
        self.threshold.valueChanged.connect(lambda v: self.lbl_threshold.setText(str(v)))
        thr_row = QWidget()
        thr_lay = QHBoxLayout(thr_row)
        thr_lay.setContentsMargins(0, 0, 0, 0)
        thr_lay.setSpacing(6)
        thr_lay.addWidget(self.threshold, 1)
        thr_lay.addWidget(self.lbl_threshold)
        lay.addWidget(self._pair("灰度阈值", thr_row), 0, 0, 1, 2)

        self.chk_invert = QCheckBox("检测暗色目标")
        self.chk_invert.setToolTip("反相：把暗色像素当作目标")
        self.chk_otsu = QCheckBox("OTSU 自动阈值")
        self.chk_otsu.setToolTip("忽略固定阈值，由 OTSU 自动计算")
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        mode_row.addWidget(self.chk_invert)
        mode_row.addWidget(self.chk_otsu)
        mode_row.addStretch(1)
        lay.addLayout(mode_row, 1, 0, 1, 2)

        self.spin_min_area = self._spin(1, 100000, 50)
        self.spin_min_area.setToolTip("小于该面积的亮块视为噪点，不生成目标")
        self.spin_dup = self._spin(0, 200, 15)
        self.spin_dup.setToolTip("两点距离小于该值时只保留一个，避免重复点击")
        self.spin_grid = self._spin(3, 200, 20)
        self.spin_grid.setToolTip("多点模式下点阵的行列间距")
        self.spin_max_points = self._spin(10, 5000, 800)
        self.spin_max_points.setToolTip("单帧最多点击多少个点，防止误点过多")
        lay.addWidget(self._pair("最小面积", self.spin_min_area), 2, 0)
        lay.addWidget(self._pair("去重半径", self.spin_dup), 2, 1)
        lay.addWidget(self._pair("点阵间距", self.spin_grid), 3, 0)
        lay.addWidget(self._pair("单帧上限", self.spin_max_points), 3, 1)

        self.combo_order = QComboBox()
        self.combo_order.addItem("从上到下、从左到右", "y_x")
        self.combo_order.addItem("从左到右、从上到下", "x_y")
        self.combo_order.addItem("距左上角由近到远", "corner")
        self.combo_order.setToolTip("同一帧内多个目标的点击先后次序")
        lay.addWidget(self._pair("点击顺序", self.combo_order), 4, 0, 1, 2)

        self.chk_grid = QCheckBox("多点模式")
        self.chk_grid.setChecked(True)
        self.chk_grid.setToolTip("在区域内生成等距点阵，适合密集小目标")
        self.chk_dist_center = QCheckBox("距离变换取中心")
        self.chk_dist_center.setChecked(True)
        self.chk_dist_center.setToolTip("用距离变换取目标内部最中心的位置，避免点到边缘")
        last_row = QHBoxLayout()
        last_row.setSpacing(12)
        last_row.addWidget(self.chk_grid)
        last_row.addWidget(self.chk_dist_center)
        last_row.addStretch(1)
        lay.addLayout(last_row, 5, 0, 1, 2)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        return card

    def _build_click_card(self):
        card = self._card("点击与验证")
        lay = QGridLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(6)

        self.spin_interval = self._dspin(0.05, 2.0, 0.15)
        self.spin_interval.setToolTip("两次点击之间的等待时间")
        self.spin_verify = self._dspin(0.05, 2.0, 0.25)
        self.spin_verify.setToolTip("点击后等待多久再截图检测红色反馈")
        self.spin_retries = self._spin(0, 10, 3)
        self.spin_retries.setToolTip("一次点击未变红时的最大重试次数")
        self.spin_red_px = self._spin(1, 2000, 12)
        self.spin_red_px.setToolTip("点周围出现多少红像素就判定点击成功")
        self.spin_red_ratio = self._spin(1, 90, 15)
        self.spin_red_ratio.setToolTip("轮廓内红色占比超过该值时视为已完成，直接跳过")
        lay.addWidget(self._pair("点击间隔", self.spin_interval), 0, 0)
        lay.addWidget(self._pair("验证等待", self.spin_verify), 0, 1)
        lay.addWidget(self._pair("最大重试", self.spin_retries), 1, 0)
        lay.addWidget(self._pair("红像素", self.spin_red_px), 1, 1)
        lay.addWidget(self._pair("红区占比", self.spin_red_ratio), 2, 0)

        self.chk_autostop = QCheckBox("完成后自动停止")
        self.chk_autostop.setChecked(True)
        self.chk_autostop.setToolTip("循环模式下：点击过目标后再次检测不到目标就结束")
        lay.addWidget(self.chk_autostop, 2, 1)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        return card

    def _build_mode_card(self):
        card = self._card("运行模式与快捷键")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.chk_auto = QCheckBox("自动模式（只截一次图）")
        self.chk_auto.setToolTip("只截一次图，点完该帧全部目标后按一次翻页键并自动结束")
        self.chk_auto.toggled.connect(self._on_auto_toggled)
        lay.addWidget(self.chk_auto)

        self.combo_dir = QComboBox()
        self.combo_dir.addItem("向下翻页（PageDown）", "down")
        self.combo_dir.addItem("向上翻页（PageUp）", "up")
        self.combo_dir.setToolTip("自动模式结束时按下的翻页键；与上面的点击顺序互不影响")
        self.combo_dir.setEnabled(False)
        lay.addWidget(self._pair("翻页方向", self.combo_dir))

        hint = QLabel(
            "自动模式：只截一次图 → 点完该帧全部目标 → 按一次翻页键 → 自动结束；"
            "该帧没有识别到目标时不按键。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        keys = QLabel("快捷键（窗口不在前台也有效）：F9 预览　F10 开始　F11 暂停/继续　F8 停止")
        keys.setWordWrap(True)
        keys.setObjectName("Hint")
        lay.addWidget(keys)
        return card

    def _build_advanced_card(self):
        card = self._card("高级参数")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.btn_adv = QPushButton("显示高级参数")
        self.btn_adv.setObjectName("Ghost")
        self.btn_adv.setCheckable(True)
        self.btn_adv.toggled.connect(self._on_adv_toggled)
        lay.addWidget(self.btn_adv, 0, Qt.AlignmentFlag.AlignLeft)

        self.adv_box = QWidget()
        adv = QGridLayout(self.adv_box)
        adv.setContentsMargins(0, 0, 0, 0)
        adv.setHorizontalSpacing(8)
        adv.setVerticalSpacing(6)
        self.spin_verify_radius = self._spin(4, 80, 12)
        self.spin_verify_radius.setToolTip("判断“已变红”时，取点击点周围多大的方形范围统计红像素")
        adv.addWidget(self._pair("验证半径", self.spin_verify_radius), 0, 0, 1, 2)
        note = QLabel("验证半径越大越不容易误判，但相邻目标已变红时更容易漏点，一般保持 12 即可。")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        adv.addWidget(note, 1, 0, 1, 2)
        adv.setColumnStretch(0, 1)
        self.adv_box.setVisible(False)
        lay.addWidget(self.adv_box)
        return card

    def _build_run_column(self):
        """右侧主区：预览 / 状态 / 日志 / 按钮。"""
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.preview = QLabel("预览区\n（点“预览”或“开始”后显示识别结果）")
        self.preview.setObjectName("Preview")
        self.preview.setMinimumHeight(260)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setWordWrap(True)
        lay.addWidget(self.preview, 1)

        self.lbl_stats = QLabel("剩余目标：-    已点击：0    失败：0")
        self.lbl_stats.setObjectName("Stats")
        lay.addWidget(self.lbl_stats)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        lay.addWidget(self.log_view)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_preview = QPushButton("预览 (F9)")
        self.btn_preview.setToolTip("只识别并画框，不点击（F9）")
        self.btn_calibrate = QPushButton("自动校准")
        self.btn_calibrate.setToolTip("按当前画面自动推算阈值、面积、红点等参数")
        self.btn_start = QPushButton("开始 (F10)")
        self.btn_start.setObjectName("Primary")
        self.btn_start.setToolTip("开始自动点击（F10）")
        self.btn_pause = QPushButton("暂停 (F11)")
        self.btn_pause.setToolTip("暂停 / 继续（F11）")
        self.btn_pause.setEnabled(False)
        self.btn_stop = QPushButton("停止 (F8)")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setToolTip("立即停止（F8）")
        self.btn_stop.setEnabled(False)
        for btn in (
            self.btn_preview,
            self.btn_calibrate,
            self.btn_start,
            self.btn_pause,
            self.btn_stop,
        ):
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self.btn_preview.clicked.connect(self.preview_once)
        self.btn_calibrate.clicked.connect(self.calibrate_region)
        self.btn_start.clicked.connect(self.start_click)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.stop_click)
        return col

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

    @staticmethod
    def _card(title):
        """统一风格的卡片（QGroupBox）；具体布局由调用方挂载。"""
        return QGroupBox(title)

    @staticmethod
    def _pair(label, widget):
        """把「标签 + 控件」压成一格，横向排列，减少纵向占用。"""
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lbl = QLabel(label)
        lbl.setFixedWidth(56)
        lay.addWidget(lbl)
        lay.addWidget(widget, 1)
        return box

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
            verify_radius=self.spin_verify_radius.value(),
            red_ratio_threshold=self.spin_red_ratio.value() / 100.0,
            auto_stop=self.chk_autostop.isChecked(),
            auto_mode=self.chk_auto.isChecked(),
            page_direction=self.combo_dir.currentData(),
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
        self.spin_verify_radius.setValue(suggestions["verify_radius"])
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
        self._worker.paused.connect(self._on_paused)
        self._set_running(True)
        if cfg.auto_mode:
            key = "PageUp" if cfg.page_direction == "up" else "PageDown"
            self._append_log(f"开始自动模式…（只截一次图，点完该帧后按 {key} 并结束）")
        else:
            self._append_log("开始循环点击…")
        self._append_log("快捷键：F11 暂停/继续，F8 停止；鼠标移到屏幕左上角为紧急停止。")
        self._worker.start()

    def stop_click(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
        self._set_running(False)

    def toggle_pause(self):
        """暂停 / 继续当前运行（按钮或 F11）。"""
        if not (self._worker and self._worker.isRunning()):
            self._append_log("当前没有正在运行的任务，无需暂停。")
            return
        self._worker.toggle_pause()

    def _on_paused(self, paused):
        self.btn_pause.setText("继续 (F11)" if paused else "暂停 (F11)")
        self._append_log("已暂停（F11 继续）" if paused else "已继续")

    def _on_auto_toggled(self, checked):
        self.combo_dir.setEnabled(checked)
        self.chk_autostop.setEnabled(not checked)
        if checked:
            self._append_log("已开启自动模式：只截一次图，点完该帧全部目标后按一次翻页键并结束。")

    def _on_adv_toggled(self, checked):
        self.adv_box.setVisible(checked)
        self.btn_adv.setText("隐藏高级参数" if checked else "显示高级参数")

    def _on_finished(self, clicked, failed):
        self._set_running(False)
        self._append_log(f"自动完成：成功 {clicked}，失败 {failed}")

    def _set_running(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_preview.setEnabled(not running)
        self.btn_calibrate.setEnabled(not running)
        self.btn_pick.setEnabled(not running)
        self.chk_auto.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_pause.setText("暂停 (F11)")
        self.btn_stop.setEnabled(running)

    def _update_stats(self, remaining, clicked, failed):
        self.lbl_stats.setText(
            f"剩余目标：{remaining}    已点击：{clicked}    失败：{failed}"
        )

    # ---------------- 热键 ----------------
    def _start_hotkeys(self):
        try:
            self._hotkey_thread = HotkeyThread(
                {
                    "<f8>": "stop",
                    "<f9>": "preview",
                    "<f10>": "start",
                    "<f11>": "pause",
                }
            )
            self._hotkey_thread.triggered.connect(self._on_hotkey)
            self._hotkey_thread.start()
            self._append_log(
                "已启用全局热键：F9 预览 / F10 开始 / F11 暂停 / F8 停止（窗口不在前台也有效）"
            )
        except Exception as exc:
            self._append_log(f"热键启动失败：{exc}")

    def _on_hotkey(self, name):
        if name.startswith("hotkey_error:"):
            self._append_log(f"热键异常：{name[len('hotkey_error:'):]}")
            return
        if name == "stop":
            if self._worker and self._worker.isRunning():
                self._append_log("F8 停止")
            else:
                self._append_log("F8（当前没有运行中的任务）")
            self.stop_click()
        elif name == "preview":
            self._append_log("F9 预览")
            self.preview_once()
        elif name == "start":
            self._append_log("F10 开始")
            self.start_click()
        elif name == "pause":
            self._append_log("F11 暂停/继续")
            self.toggle_pause()

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
    app.setStyleSheet(STYLE_SHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()