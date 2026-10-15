# capture.py

## 1. 用途

屏幕截图与 DPI 处理：把指定屏幕矩形抓成 RGB 的 `numpy` 数组，并让进程进入 DPI 感知状态，使截图坐标与 pyautogui 点击坐标一致。

## 2. 变量/字段清单

| 名字 | 含义 | 类型 | 格式与大小 |
|---|---|---|---|
| `_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2` | Windows「每显示器 DPI 感知 V2」上下文常量 | int | 固定 `-4` |
| `ScreenCapture.sct` | mss 实例 | `mss.mss` | 进程内单例式持有 |
| `ScreenCapture.screen_bounds` | 所有显示器组成的虚拟桌面矩形 | tuple[int,int,int,int] | (left, top, width, height)，物理像素 |
| `grab()` 返回 | 抓取到的图像 | `numpy.ndarray` | `uint8`，形状 `(height, width, 3)`，**RGB** 通道序 |

## 3. 输入/输出

- 输入：`set_dpi_awareness()` 无参；`grab(region)` 收 4 元组 `(left, top, width, height)`（屏幕物理像素）；`close()` 无参。
- 输出：`grab()` 返回 RGB ndarray（mss 原图是 BGRA，经 `cv2.cvtColor(..., cv2.COLOR_BGRA2RGB)` 转换）。
- 读文件：无。写文件：无（不保存任何截图）。
- 屏幕交互：`self.sct.grab({...})` 读取屏幕像素（只读，不产生任何输入事件）。
- 主要符号：`set_dpi_awareness()`、`ScreenCapture.__init__()`、`ScreenCapture.grab()`、`ScreenCapture.close()`。
- 被谁使用：`main.py` 的 `main()` 调 `set_dpi_awareness()`；`worker.py` 持有一个 `ScreenCapture` 实例做区域截图与点击后的验证小图截图。
- 错误口径：`width<=0` 或 `height<=0` 时 `grab()` 抛 `ValueError("检测区域宽高必须为正")`；`close()` 吞掉所有异常。

## 4. 【待确认】

- DPI 感知只尝试 `SetProcessDpiAwarenessContext(-4)`，失败后退到 `shcore.SetProcessDpiAwareness(2)`，再失败就**静默忽略**（`pass`）——此时高 DPI 屏上点击可能偏移，界面上没有提示。未在多显示器混合 DPI 的机器上实测。
- `screen_bounds` 取 `mss.monitors[0]`（整个虚拟桌面），而区域框选按主屏缩放换算；多屏坐标合法性只由 `main.py` 的区域校验兜底。
- `grab()` 每次调用都新开一次 mss 抓取，未做缓冲；粘贴到目标窗口上的遮挡无法从截图中分辨。
