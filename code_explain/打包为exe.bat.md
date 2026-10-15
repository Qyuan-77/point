# 打包为exe.bat

## 1. 用途

**可选**工具：用 PyInstaller 把 `main.py` 打成独立单文件 exe（`dist\TargetClicker.exe`），无控制台窗口，目标机器不需要 Python/conda，可直接拷走或重命名。

注意：本会话**没有实际执行过打包**（见第 4 节），脚本只做了静态检查（CRLF/ASCII、分支逻辑、路径存在性）。需要联网、耗时数分钟，由用户自行双击决定。

## 2. 变量/字段清单

| 名字 | 含义 | 取值 |
|---|---|---|
| `%~dp0` | 本脚本所在目录 | `D:\seeg\point\` |
| `PY` | 打包用的解释器绝对路径（硬编码） | `E:\anconda\envs\point_clicker\python.exe` |
| `PYTHONIOENCODING` | `utf-8` | `utf-8` |
| `TargetClicker` | 产物名（`--name` 的值），决定 `TargetClicker.spec` 与 `dist\TargetClicker.exe` | 字符串 |
| 标签 | `:install` 装 PyInstaller；`:clean` 清旧产物；`:ok` 成功；`:pip_fail` / `:build_fail` / `:no_py` / `:no_main` 失败 | — |

实际调用的打包参数（第 45 行）：

```
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name TargetClicker main.py
```

`--windowed` 相当于用 `pythonw` 启动（不弹控制台）；想加快启动把 `--onefile` 换成 `--onedir`。

## 3. 输入/输出

- 输入：无命令行参数。
- 读：`%PY%`、`main.py`；第 1 步会尝试 `import PyInstaller`，缺了就联网 `%PY% -m pip install pyinstaller`（有 `pause` 让人确认）。
- 写：先 `rmdir /s /q "build"`、`rmdir /s /q "dist"`、`del /q "TargetClicker.spec"`，再生成 `build\`、`dist\TargetClicker.exe`、`TargetClicker.spec`。
- 输出：四步进度（检查 PyInstaller / 清理旧产物 / 打包中并提示可能几分钟 / 结果路径），失败时打印原因并 `pause`。
- 退出码：成功 `0`，失败 `1`。

## 4. 【待确认】

- **有破坏性**：会无条件删除项目目录下的 `build\`、`dist\` 与 `TargetClicker.spec`。若项目里另有叫 `build` / `dist` 的重要目录，请先改名——本项目当前没有这两个目录。
- **未验证**：本会话未安装 PyInstaller（实测 `import PyInstaller` 抛 `ModuleNotFoundError`），也未执行打包；产物能否正常运行、体积与启动速度都**没有实测数据**。
- `--onefile` 产物首次运行要解压到临时目录（约慢 3~10 秒）；PyQt6 + OpenCV 的单文件产物通常上百 MB。
- 打包只处理 `main.py` 的依赖链；本项目数据文件/资源没有额外需要 `--add-data` 的东西（无图标、无外部配置）。
- 同样遵守 `.bat` 的 **ASCII + CRLF** 约定（原因见 `run.bat.md` 第 4 节）。
