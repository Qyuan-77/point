"""ui_smoke_offscreen: 离屏实例化主窗口，检查控件/配置/状态联动，并导出界面截图。

不弹窗、不点击、不按键，可随时重跑（改 UI 后先跑它）。
运行：
    $env:PYTHONIOENCODING='utf-8'
    & 'E:\\anconda\\envs\\point_clicker\\python.exe' ui_smoke_offscreen.py [截图输出路径]
截图默认写到系统临时目录，路径会打印出来；离屏渲染缺少字体时中文会显示为方框，属正常现象。
"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication  # noqa: E402

import main as app_main  # noqa: E402

app = QApplication(sys.argv)
app.setStyleSheet(app_main.STYLE_SHEET)
win = app_main.MainWindow()
win.show()
app.processEvents()

checks = []


def chk(name, cond, extra=""):
    checks.append((name, bool(cond), extra))


chk("chk_auto/combo_dir/spin_verify_radius/btn_pause/adv 均存在",
    all(hasattr(win, a) for a in
        ("chk_auto", "combo_dir", "spin_verify_radius", "btn_pause", "btn_adv", "adv_box")))
chk("默认自动模式关闭", win.chk_auto.isChecked() is False)
chk("默认翻页方向禁用", win.combo_dir.isEnabled() is False)
chk("默认暂停按钮禁用", win.btn_pause.isEnabled() is False)
chk("默认开始按钮可用", win.btn_start.isEnabled() is True)
chk("默认停止按钮禁用", win.btn_stop.isEnabled() is False)

win.chk_auto.setChecked(True)
app.processEvents()
chk("自动模式开启后翻页方向可用", win.combo_dir.isEnabled() is True)
chk("自动模式下停止方式置灰", win.chk_autostop.isEnabled() is False)

win.combo_dir.setCurrentIndex(1)          # 向上翻页
cfg = win._make_config()
chk("cfg.auto_mode=True", cfg.auto_mode is True)
chk("cfg.page_direction=up", cfg.page_direction == "up", repr(cfg.page_direction))
chk("cfg.verify_radius 已接入", cfg.verify_radius == 12, cfg.verify_radius)
chk("cfg.click_order 正常", cfg.click_order == "y_x", repr(cfg.click_order))
chk("cfg.region 正常", cfg.region == (0, 0, 800, 600), cfg.region)

win.btn_adv.setChecked(True)
app.processEvents()
chk("高级参数展开可见", win.adv_box.isVisible() is True)
chk("高级参数按钮文案切换", win.btn_adv.text() == "隐藏高级参数", win.btn_adv.text())

win._on_paused(True)
app.processEvents()
chk("暂停后按钮显示继续", win.btn_pause.text() == "继续 (F11)", win.btn_pause.text())
win._on_paused(False)
app.processEvents()
chk("继续后按钮显示暂停", win.btn_pause.text() == "暂停 (F11)", win.btn_pause.text())
win.toggle_pause()                        # 无任务时应安全返回

win._set_running(True)
app.processEvents()
chk("运行中暂停按钮可用", win.btn_pause.isEnabled() is True)
chk("运行中自动模式开关置灰", win.chk_auto.isEnabled() is False)
chk("运行中开始按钮禁用", win.btn_start.isEnabled() is False)
win._set_running(False)

win.resize(960, 680)
app.processEvents()
print("window size:", win.size().width(), win.size().height())
shot = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    tempfile.gettempdir(), "ui_smoke_offscreen.png"
)
win.grab().save(shot)
print("screenshot:", shot)

print("---- 日志窗口内容 ----")
print(win.log_view.toPlainText())

ok = True
for name, res, extra in checks:
    print(("PASS " if res else "FAIL "), name, extra)
    ok = ok and res
print("RESULT", "ALL_PASS" if ok else "HAS_FAILURE")

win.close()
app.processEvents()
