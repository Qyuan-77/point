# code_explain — 本文件夹代码文件清单

代码目录：`D:\seeg\point`（单文件夹项目，无子目录）。每个代码文件对应一份同名说明。

| 代码文件 | 一句话作用 | 说明文件 |
|---|---|---|
| main.py | PyQt6 GUI 入口：区域框选、参数面板、校准/预览/开始/暂停/停止、全局热键 | main.py.md |
| worker.py | 后台 QThread：循环模式与自动模式（只截一次图）的截图→点击→红色验证，含暂停 | worker.py.md |
| detector.py | 检测算法：灰度/Otsu 分割 + 连通域 + 红色完成态排除 + 自动校准参数推断 | detector.py.md |
| capture.py | mss 截图封装与 Windows DPI 感知设置 | capture.py.md |
| config.py | `Config` 数据类：全部运行参数及默认值 | config.py.md |
| run.bat | 一键启动脚本（带控制台，出错时停住显示报错） | run.bat.md |
| 创建桌面快捷方式.bat | 把本目录的 .lnk 复制到桌面 | 创建桌面快捷方式.bat.md |
| 打包为exe.bat | PyInstaller 打包独立 exe（可选，本会话未执行） | 打包为exe.bat.md |

非代码文件：`目标颜色自动点击器.lnk`（快捷方式，用 pythonw 静默启动）、`run.bat.bak_lf-broken`（旧 run.bat 备份，LF 行尾已废弃）、`requirements.txt`（依赖清单）、`README.md`（使用说明）、`deepseek_help\scripts\`（不点真鼠标的验证脚本）。

## .bat 硬约定（改这些文件前必读）

所有 `.bat` 必须 **CRLF 行尾 + 纯 ASCII 内容**，且不得在文件中间 `chcp`；中文说明写在 `README.md` 里。原因：cmd.exe 对 LF 行尾/非 ASCII 的批处理会切错行，实测报「不是内部或外部命令」，复现与四组对照实验见 `run.bat.md` 第 4 节。

## 跨文件约定（改代码前先看）

- **坐标**：统一为屏幕**物理像素**。`capture.set_dpi_awareness()` 在 `main()` 最早调用；`detector.Detector.detect()` 返回的是**检测区域内的局部坐标**，`worker` 点击时加上 `cfg.region` 的 `left/top` 换算成屏幕坐标。
- **线程模型**：主线程只做 UI；`worker.ClickWorker`（QThread）做截图/点击，两者只用 Qt 信号通信（`frame_ready` / `log` / `stats` / `finished_ok` / `paused`），UI 不直接读 worker 内部状态。
- **两种运行模式**：`cfg.auto_mode=False` 走循环模式（反复截图直到无目标），`True` 走自动模式（只截一次图 → 点完该帧 → 按一次翻页键 → 结束）。两种模式共用 `_click_and_verify`，所以验证与重试口径一致。
- **暂停**：统一由 `ClickWorker._wait_if_paused()` 在 50 ms 轮询里挂起；所有长等待都走 `_sleep()`，因此暂停/停止对全流程有效。
- **参数单一来源**：只有 `Config` 存参数；GUI 只是它的编辑器（`MainWindow._make_config()`），`detector`/`worker` 都不保存配置。
