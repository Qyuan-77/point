# config.py

## 1. 用途

定义全部运行参数的 `Config` 数据类（默认值集中在此，GUI 只负责编辑它）。

## 2. 变量/字段清单

`@dataclass class Config`，字段名与分组注释一一对应；改默认值只需改这里。

| 名字 | 含义 | 类型 | 默认值 / 取值 |
|---|---|---|---|
| region | 检测区域（屏幕物理像素，left, top, width, height） | tuple[int,int,int,int] | (0, 0, 1920, 1080) |
| gray_threshold | 灰度阈值：大于该值视为目标 | int | 180（0~255） |
| invert_bright | True 表示检测暗色目标 | bool | False |
| use_otsu | True 表示用 OTSU 自动阈值（覆盖 gray_threshold） | bool | False |
| min_area | 最小目标面积（像素），过滤噪声 | int | 50 |
| duplicate_distance | 与已点击点距离小于该值视为重复（仅循环模式去重） | int | 15 |
| click_order | 点击顺序：y_x=从上到下/从左到右；x_y=从左到右/从上到下；corner=距左上角由近到远 | str | "y_x" |
| generate_grid | True 时在白色亮块内按等距行列生成多个点击点（多点模式） | bool | True |
| grid_spacing | 点阵间距（像素） | int | 20 |
| max_points | 单帧最多生成的点数（防溢出） | int | 800 |
| use_distance_center | 用距离变换取目标内部离边缘最远的点作为点击中心 | bool | True |
| click_interval | 相邻点击的最小间隔（秒） | float | 0.15 |
| verify_delay | 点击后等待变红的时间（秒） | float | 0.25 |
| max_retries | 点击后无红色反馈的最大重试次数 | int | 3 |
| red_pixel_threshold | 点击点周围红像素数 ≥ 该值判定成功 | int | 12 |
| verify_radius | 红色验证区域半径（像素） | int | 12 |
| auto_mode | True 时走自动模式：只截一次图，点完该帧全部目标后按翻页键并结束 | bool | False |
| page_direction | 自动模式结束时的翻页键：down=PageDown；up=PageUp | str | "down" |
| red_ratio_threshold | 轮廓框内红色占比超过该值视为已完成 | float | 0.15 |
| scan_interval | 循环模式下无目标时的轮询间隔（秒） | float | 0.2 |
| auto_stop | 循环模式：全部完成后自动停止 | bool | True |

注：`detector`/`worker` 用 `getattr(cfg, 名字, 默认)` 读取 `generate_grid`、`click_order`、`auto_mode`，所以外部传入的简化配置对象也能用。

## 3. 输入/输出

- 读文件：无。
- 写文件：无（本文件不落盘任何配置；每次运行都是「默认值 + GUI 编辑」，不记忆上次设置）。
- 被谁读取：`main.py`（`_make_config()` 按控件填字段、`start_click()`/`preview_once()` 作为默认值模板）、`worker.py`（全流程读取）、`detector.py`（分割与过滤读取）。
- 被谁写入：`main.py` 只写入自己新建的实例，不修改类默认值。

## 4. 【待确认】

- 参数**不会持久化**（关掉程序即丢失改动）——这是当前实现，不是 bug；若要「记住上次设置」需另加配置文件，尚未实现。
- `verify_radius` 在 2026-10-14 之前是「死参数」（GUI 无控件、`_make_config()` 未传）；现已由「高级参数」里的 `spin_verify_radius` 接入，默认值保持 12 不变。
- 字段的**语义联动**（如 `use_otsu=True` 时 `gray_threshold` 被忽略、自动模式忽略 `auto_stop`）由调用方保证，`Config` 本身不做校验。
