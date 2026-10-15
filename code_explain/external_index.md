# external_index — 本文件夹**实际引用到**的外部代码文件

本项目所有代码都在 `D:\seeg\point` 一个文件夹里，**没有**本文件夹之外的项目代码文件。
下表只列出被直接 import 的第三方包/标准库（用于依赖核对与升级排查），每项一句话。

## 第三方包

- `PyQt6`（QtWidgets/QtCore/QtGui）：`main.py` 全部界面与 `worker.py` 的 `QThread`/`pyqtSignal`。
- `cv2`（opencv-python）：`detector.py` 的分割/形态学/连通域/距离变换，`worker.py` 的预览绘制，`capture.py` 的颜色转换。
- `numpy`：`detector.py` 的掩码运算与统计（`capture.py` 只用其 `uint8` 转换）。
- `mss`：`capture.py` 的屏幕抓取（BGRA 位图）。
- `pyautogui`：`worker.py` 的真实点击与翻页按键（`click` / `press` / `FailSafeException`）。
- `pynput`：`main.py` 的全局热键监听（`keyboard.GlobalHotKeys`）。
- `pillow`（Pillow）：**仅在 `requirements.txt` 中声明，代码未直接 import**（Qt 自身负责图像显示），保留是为满足运行环境约定。
- `PyInstaller`：**仅构建期使用**，由 `打包为exe.bat` 以 `%PY% -m PyInstaller` 调用，应用代码不 import；未安装时该脚本会先联网 `pip install pyinstaller`（本会话未执行打包，PyInstaller 未安装）。

## 标准库

- `ctypes`：`capture.py` 调 Windows API 设置 DPI 感知。
- `dataclasses`：`config.py` 的 `Config`。
- `time`：`worker.py` 的节流/暂停轮询（`time.time` / `time.sleep`）。
