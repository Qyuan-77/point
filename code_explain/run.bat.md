# run.bat

## 1. 用途

双击启动脚本（**带控制台**版）：切到脚本所在目录，用绝对路径找到 conda 环境 `point_clicker` 的 `python.exe` 运行 `main.py`。出错时窗口停住，方便把报错原文发出来；想要「不弹控制台窗口」的启动方式，用同目录的 `目标颜色自动点击器.lnk`（它跑 `pythonw.exe`）。

文件硬约定：**CRLF 行尾 + 纯 ASCII 内容 + 不在文件中途 `chcp`**（实测根因见第 4 节）。

## 2. 变量/字段清单

| 名字 | 含义 | 取值 |
|---|---|---|
| `%~dp0` | 本脚本所在目录（含尾反斜杠） | `D:\seeg\point\` |
| `PY` | 运行用的解释器绝对路径（硬编码） | `E:\anconda\envs\point_clicker\python.exe` |
| `PYTHONIOENCODING` | 强制 Python 的 stdio 用 UTF-8，中文日志/报错不乱码 | `utf-8` |
| `QT_LOGGING_RULES` | 屏蔽 Qt 的 `qt.qpa.window` 类别日志（那行 DPI 提示无意义） | `qt.qpa.window=false` |
| `RC` | `main.py` 的退出码 | 整数 |
| `%CD%` | 当前工作目录（`cd /d "%~dp0"` 之后即项目目录） | `D:\seeg\point` |
| 标签 | `:no_main` 缺 `main.py`；`:launch` 正常启动；`:done` 正常退出 | — |

全脚本用 `goto :label` 组织，不用括号块（括号块在 cmd 下更易被错误解析）。

## 3. 输入/输出

- 输入：无命令行参数，无参数解析。
- 读文件：`main.py`（存在性检查后运行）、`%PY%`（存在性检查）；间接读 `requirements.txt` 所列依赖。
- 写文件：无。
- 输出（控制台）：启动横幅（解释器路径、工作目录、退出方式「按 F8 或关掉窗口」）；三个错误分支各自打印原因并 `pause`——① 找不到解释器（提示建环境或手改 `PY`）、② 当前目录没有 `main.py`、③ `main.py` 以非 0 退出（打印退出码，请把上方报错发给助手）。
- 退出码：正常 `0`；前两个错误分支 `1`；`main.py` 非 0 时透传其退出码。

## 4. 【待确认】

- `PY` 是**硬编码**的：换机器或改 conda 环境名后必须同步改这一行（`README.md`「环境」一节与此对应）。
- **为什么全 ASCII + CRLF（本会话实测根因）**：旧版 `run.bat` 是 LF 行尾 + 中文注释/中文 echo，双击后实际报错为 `'E:\anconda\envs\point_clicker\python.exe" (' 不是内部或外部命令`、`系统找不到指定的路径。`、`'痌' 不是内部或外部命令`。四组对照实验结论：**LF + 非 ASCII ⇒ 坏**；CRLF + 中文 ⇒ 正常；LF + 纯 ASCII ⇒ 正常；CRLF + 纯 ASCII ⇒ 正常。另测出文件中途 `chcp 65001` 后再出现非 ASCII 行会让 cmd 再次失去行同步（报 `'涓恒€孶TF-8' 不是内部或外部命令`）。⇒ 本项目所有 `.bat` 一律 **ASCII + CRLF 且不写 `chcp`**，中文说明只放 README。
- 只是「解释器存在性」检查：环境在但依赖缺包时脚本不检查，报错只出现在控制台里（依赖清单见 `requirements.txt`）。
- 该脚本已实测：真实双击等价路径能启动 GUI，正常退出时控制台无输出、退出码 0（屏蔽 DPI 提示后 stderr 为空）。
