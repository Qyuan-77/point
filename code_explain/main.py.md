# main.py

## 1. 用途

PyQt6 单窗口 GUI 入口：框选屏幕检测区域、编辑全部运行参数、自动校准/预览/开始/暂停/停止，并注册全局热键；程序启动时先设置 DPI 感知。

## 2. 变量/字段清单

### 2.1 模块级

| 名字 | 含义 | 类型 | 说明 |
|---|---|---|---|
| `STYLE_SHEET` | 浅色卡片风样式表 | str | 全局 QSS：根底色、卡片（QGroupBox）、输入框/按钮/滑块/复选框、`#Primary`（蓝底开始）、`#Danger`（描边停止）、`#Ghost`（高级参数按钮）、`#Preview`/`#Stats`/`#Hint` 标签 |
| `main()` | 程序入口 | 函数 | `set_dpi_awareness()` → `QApplication` → `setStyleSheet` → `MainWindow.resize(960, 680)` → `show()` |
| `RegionSelector` | 全屏半透明框选覆盖层 | `QWidget` | 拖拽/按下-移动-释放出矩形，`region_selected` 信号回传**物理像素** 4 元组；Esc/右键取消；用 `devicePixelRatioF()` 换算 |
| `HotkeyThread` | 全局热键监听线程 | `QThread` | 包 `pynput.keyboard.GlobalHotKeys(hotkeys)`；`hotkeys` 形如 `{"<f8>": "stop"}` |

### 2.2 MainWindow 控件

| 名字 | 含义 | 类型 | 取值范围 / 默认值 |
|---|---|---|---|
| `spin_x` / `spin_y` | 检测区域左上角（屏幕物理像素） | QSpinBox | 0~20000 / 0 |
| `spin_w` / `spin_h` | 检测区域宽 / 高 | QSpinBox | 1~20000 / 800、600 |
| `btn_pick` | 「框选区域」按钮 | QPushButton | 打开 `RegionSelector` |
| `threshold` | 灰度阈值滑块 | QSlider | 0~255（初值 180） |
| `lbl_threshold` | 阈值数值显示 | QLabel | 随滑块更新 |
| `chk_invert` | 「检测暗色目标」 | QCheckBox | False |
| `chk_otsu` | 「OTSU 自动阈值」 | QCheckBox | False |
| `spin_min_area` | 最小目标面积 | QSpinBox | 1~100000 / 50 |
| `spin_dup` | 去重半径 | QSpinBox | 0~200 / 15 |
| `spin_grid` | 点阵间距 | QSpinBox | 3~200 / 20 |
| `spin_max_points` | 单帧最多点数 | QSpinBox | 10~5000 / 800 |
| `combo_order` | 点击顺序 | QComboBox | items：`("从上到下、从左到右","y_x")`、`("从左到右、从上到下","x_y")`、`("距左上角由近到远","corner")` |
| `chk_grid` | 「多点模式」 | QCheckBox | True |
| `chk_dist_center` | 「距离变换取中心」 | QCheckBox | True |
| `spin_interval` | 点击间隔(秒) | QDoubleSpinBox | 0.05~2.0 / 0.15 |
| `spin_verify` | 验证等待(秒) | QDoubleSpinBox | 0.05~2.0 / 0.25 |
| `spin_retries` | 最大重试次数 | QSpinBox | 0~10 / 3 |
| `spin_red_px` | 成功所需红像素 | QSpinBox | 1~2000 / 12 |
| `spin_red_ratio` | 红区排除占比(%) | QSpinBox | 1~90 / 15（传给 `Config.red_ratio_threshold` 时 /100） |
| `chk_autostop` | 「完成后自动停止」 | QCheckBox | True |
| `chk_auto` | 「自动模式（只截一次图）」 | QCheckBox | False |
| `combo_dir` | 翻页方向 | QComboBox | items：`("向下翻页（PageDown）","down")`、`("向上翻页（PageUp）","up")`；未开自动模式时禁用 |
| `btn_adv` | 「显示/隐藏高级参数」 | QPushButton | checkable，`#Ghost` 样式 |
| `adv_box` | 高级参数容器 | QWidget | 默认隐藏 |
| `spin_verify_radius` | 验证区域半径 | QSpinBox | 4~80 / 12（高级参数；修掉了原先的“死参数”问题） |
| `preview` | 预览图区 | QLabel | `#Preview` 样式，显示 `QPixmap` |
| `lbl_stats` | 进度文本 | QLabel | `#Stats`，格式「剩余目标：N    已点击：N    失败：N」 |
| `log_view` | 日志区 | QTextEdit | 只读，末尾追加 |
| `btn_preview` / `btn_calibrate` | 「预览 (F9)」/「自动校准」 | QPushButton | — |
| `btn_start` / `btn_pause` / `btn_stop` | 「开始 (F10)」/「暂停 (F11)」/「停止 (F8)」 | QPushButton | `#Primary` / 普通 / `#Danger`；`btn_pause` 运行中在「暂停 (F11)」与「继续 (F11)」间切换 |

### 2.3 MainWindow 方法与信号连接

| 名字 | 作用 |
|---|---|
| `_build_ui()` | 组装界面：顶部区域卡片 + 左侧设置列（340 px 固定宽）+ 右侧运行列（拉伸） |
| `_build_region_card` / `_build_settings_column` / `_build_detect_card` / `_build_click_card` / `_build_mode_card` / `_build_advanced_card` / `_build_run_column` | 各卡片/列的分块构建 |
| `_spin(lo, hi, val)` / `_dspin(lo, hi, val)` | 静态工厂：建整型/浮点 SpinBox |
| `_card(title)` / `_pair(label, widget)` | 静态工厂：建卡片 QGroupBox / 建「标签+控件」一行 |
| `pick_region()` / `_on_region_selected(region)` | 打开框选覆盖层 / 回填 4 个坐标为物理像素 |
| `_make_config()` | 把全部控件读成 `Config`（含 `verify_radius`、`auto_mode`、`page_direction`） |
| `calibrate_region()` | 抓一帧调 `Detector.calibrate()`，回填建议参数（含 `spin_verify_radius`）并预览 |
| `preview_once()` | 单帧识别并显示，不点击 |
| `start_click()` | 校验区域在 `screen_bounds` 内 → 建 `ClickWorker` → 连接 `frame_ready`/`log`/`stats`/`finished_ok`/`paused` → `start()` |
| `stop_click()` | 请求停止并 `wait(5000)` |
| `toggle_pause()` / `_on_paused(paused)` | 切换暂停（F11/按钮）/ 按信号更新按钮文案与日志 |
| `_on_auto_toggled(checked)` / `_on_adv_toggled(checked)` | 自动模式下启用 `combo_dir`、置灰 `chk_autostop` / 显隐 `adv_box` 并改按钮文案 |
| `_on_finished(clicked, failed)` / `_set_running(running)` / `_update_stats(...)` | 收尾日志与状态复位 / 按运行状态启用禁用按钮 / 刷新进度标签 |
| `_start_hotkeys()` / `_on_hotkey(name)` | 启动热键线程（`<f8>`→stop、`<f9>`→preview、`<f10>`→start、`<f11>`→pause）/ 按名字派发 |
| `show_image(img)` / `_append_log(text)` | ndarray→QPixmap 显示 / 追加日志 |
| `closeEvent(event)` | 停止热键线程与工作线程后再关闭 |

## 3. 输入/输出

- 读文件：无（不读配置文件，参数全是硬编码默认值 + 界面输入）。写文件：无。
- 屏幕交互：`RegionSelector` 覆盖全屏读取鼠标框选；`pynput` 监听全局热键；真实截图与点击都在 `worker` 里做。
- 依赖符号：`capture.set_dpi_awareness`、`capture.ScreenCapture`、`detector.Detector`、`worker.ClickWorker`、`config.Config`。
- 与 worker 的接口（唯一耦合面）：信号 `frame_ready` / `log` / `stats` / `finished_ok` / `paused`，以及 `worker.stop()` / `worker.toggle_pause()` / `worker.is_paused`。
- 日志会记录热键映射，便于排查「热键不生效」。

## 4. 【待确认】

- 样式表只覆盖**浅色**主题；Windows 深色模式下 `QComboBox` 弹出的下拉列表等原生部件外观由系统决定，未适配。
- `resize(960, 680)` 后未设最小尺寸限制，屏幕小于该分辨率时右侧预览/日志会被压缩；未在小屏实测。
- 框选覆盖层的物理像素换算按 `devicePixelRatioF()`，**未在多显示器混合 DPI 环境实测**（README 也提示需手动核对坐标）。
- 全局热键 F9/F10/F11 只在离屏冒烟测试里验证了「注册与派发代码路径」，**未在真实键盘上按过**；F10 在运行中再次按下会先 `stop_click()` 再新建 worker（防重入靠按钮禁用与 `_set_running`）。
- 本次任务只按需求做了「略微简化与美化」，没有重排参数语义；`chk_autostop` 在自动模式下置灰但值仍被 `Config` 保存（自动模式不读它）。
