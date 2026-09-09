"""屏幕截图与 DPI 处理。"""

import ctypes

import cv2
import mss
import numpy as np

# Windows DPI 感知上下文常量（Per-Monitor V2）
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


def set_dpi_awareness() -> None:
    """将进程设为 DPI 感知，使 mss 截图与 pyautogui 点击使用一致的物理像素坐标。"""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            pass


class ScreenCapture:
    """基于 mss 的高速屏幕截图，返回 RGB numpy 数组（物理像素坐标）。"""

    def __init__(self) -> None:
        self.sct = mss.mss()
        mon = self.sct.monitors[0]  # 所有显示器组成的虚拟桌面
        self.screen_bounds = (
            int(mon["left"]),
            int(mon["top"]),
            int(mon["width"]),
            int(mon["height"]),
        )

    def grab(self, region) -> np.ndarray:
        left, top, width, height = region
        if width <= 0 or height <= 0:
            raise ValueError("检测区域宽高必须为正")
        shot = self.sct.grab(
            {
                "left": int(left),
                "top": int(top),
                "width": int(width),
                "height": int(height),
            }
        )
        arr = np.asarray(shot, dtype=np.uint8)  # BGRA
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)

    def close(self) -> None:
        try:
            self.sct.close()
        except Exception:
            pass