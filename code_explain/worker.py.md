# worker.py

## 1. 用途

后台 QThread 工作线程：在 UI 线程之外执行「截图 → 检测 → 点击 → 红色反馈验证」，支持**循环模式**（反复截图直到无目标）与**自动模式**（只截一次图，点完该帧后按一次翻页键并结束），并支持暂停/继续与停止。

## 2. 变量/字段清单

### 2.1 信号（只用于和 `main.py` 通信）

| 名字 | 含义 | 类型 | 载荷 |
|---|---|---|---|
| `frame_ready` | 预览图（已画绿框/红十字/编号） | `pyqtSignal(object)` | RGB `numpy.ndarray` |
| `log` | 日志文本 | `pyqtSignal(str)` | 一行字符串 |
| `stats` | 进度刷新 | `pyqtSignal(int,int,int)` | (剩余目标数, 已点击数, 失败数) |
| `finished_ok` | 线程结束 | `pyqtSignal(int,int)` | (已点击数, 失败数) |
| `paused` | 暂停状态变化 | `pyqtSignal(bool)` | True=已暂停 |

### 2.2 实例字段

| 名字 | 含义 | 类型 | 取值/上限 |
|---|---|---|---|
| `cfg` | 运行参数 | `config.Config` | 外部传入，线程不修改 |
| `_running` | 运行标志；False 时线程在下一个安全点退出 | bool | 初始 True |
| `_paused` | 暂停标志 | bool | 初始 False |
| `_capture` | 截图器 | `capture.ScreenCapture` | 线程内自建 |
| `_detector` | 检测器 | `detector.Detector` | 线程内自建 |
| `_clicked` | 已成功点击的点（**局部坐标**，近距去重兜底） | `list[tuple[int,int]]` | 只保留最近 **200** 个 |
| `_last_state` | 上一次的忙/闲状态，用于避免日志刷屏 | str / None | "idle" / "busy" |

### 2.3 方法

| 名字 | 作用 |
|---|---|
| `stop()` | 置 `_running=False`，线程在下一个安全点退出 |
| `toggle_pause()` / `resume()` / `is_paused` | 暂停切换 / 取消暂停 / 查询状态；切换时 `paused.emit()` |
| `_wait_if_paused()` | 暂停期间以 50 ms 轮询挂起；恢复或停止后返回 |
| `run()` | 入口：`getattr(cfg,"auto_mode",False)` 为真走 `_run_auto_once()`，否则 `_run_loop()`；统一捕获 `FailSafeException` 与一般异常，`finally` 里发结束日志与 `finished_ok` |
| `_run_loop()` | 循环模式：每轮抓图→`_filter_duplicates`→发预览/进度→逐个点击；无目标时 `ever_worked and cfg.auto_stop` 则自动停止，否则睡 `scan_interval` |
| `_run_auto_once()` | 自动模式：只抓一次图 → 发预览/进度 → **无目标时不按键直接结束** → 否则按序点击 → 结束后按 `pageup`/`pagedown` |
| `_click_and_verify(sx, sy)` | 点击并等待红色反馈；尝试次数 `range(1, max_retries+2)`（即最多 `max_retries+1` 次点击）；成功条件 `_count_red_near ≥ red_pixel_threshold` |
| `_count_red_near(sx, sy)` | 抓 `(max(0,sx-r), max(0,sy-r), 2r, 2r)` 小图，取红掩码像素数；`r = verify_radius` |
| `_filter_duplicates(candidates)` | 丢掉与 `_clicked` 中任一点距离平方 < `duplicate_distance²` 的候选（**仅循环模式使用**） |
| `_draw_preview(img, candidates)` | 静态方法：画绿框 + 红十字 + 左上角编号，返回新图 |
| `_mark_state(state)` | 状态变化时输出固定日志（"idle"→未发现目标，"busy"→发现目标） |
| `_log(text)` | 发送 `log` 信号 |
| `_sleep(seconds)` | 分段睡眠（每片 ≤ 50 ms）：暂停时挂起、停止时立即返回 |

## 3. 输入/输出

- 读文件：无。写文件：无（不保存截图/日志到磁盘）。
- 屏幕交互（唯一产生副作用的模块）：
  - 读：`ScreenCapture.grab(cfg.region)` 抓检测区域；`_count_red_near` 抓验证小图。
  - 写：`pyautogui.click(sx, sy)` 真实点击；自动模式结束时 `pyautogui.press("pageup" | "pagedown")`。
- 坐标换算：候选点是局部坐标，点击前 `sx = cfg.region[0] + c["x"]`、`sy = cfg.region[1] + c["y"]`。
- 发信号给 `main.py`（见 2.1），UI 侧对应 `show_image` / `_append_log` / `_update_stats` / `_on_finished` / `_on_paused`。
- 副作用与安全：鼠标被快速移到屏幕左上角时 pyautogui 抛 `FailSafeException`，线程记录日志后正常结束（不吞掉其它异常）。

## 4. 【待确认】

- `_count_red_near` 的窗口在**贴边时不对称**：起点用 `max(0, sx-r)` 裁剪，宽高仍是 `2r`，因此靠近屏幕边缘时会统计到偏移后的区域（可能含区域外像素）。这是既有行为，本次未改动。
- 自动模式**不写入 `_clicked`**（不需要跨帧去重），因此自动模式没有去重兜底；重复目标会在同一帧内被点多次（依赖 `detect` 的去重与红色判定）。
- 暂停发生在两次点击之间：已经发出的 `pyautogui.click()` 不会被回收，暂停后鼠标可能仍处于按下/弹出的中间态。
- 本次验证用假 `ScreenCapture`/假 `pyautogui` 在离屏环境跑完自动模式分支（含 0 目标不按键、方向=up、重试、暂停、停止），**未在真实目标窗口上点过真鼠标**。
