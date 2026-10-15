# detector.py

## 1. 用途

目标检测核心：灰度/Otsu 阈值分割 → 连通域 → 排除已变红的完成目标 → 输出待点击点；另提供「自动校准」，从单帧反推一套建议参数。

## 2. 变量/字段清单

| 名字 | 含义 | 类型 | 格式与大小 |
|---|---|---|---|
| `Detector._kernel` | 形态学开运算用的结构元 | `numpy.ndarray` | 3×3 `MORPH_ELLIPSE` |
| `detect()` 返回值 1：candidates | 待点击点列表，**检测区域内局部坐标** | `list[dict]` | 每项 `{"x": int, "y": int, "area": float, "bbox": (x, y, w, h)}` |
| `detect()` 返回值 2：bright | 亮目标掩码 | `numpy.ndarray` | `uint8` 0/255，与 region 同尺寸 |
| `detect()` 返回值 3：red | 红色（完成态）掩码 | `numpy.ndarray` | `uint8` 0/255，与 region 同尺寸 |
| `calibrate()` 返回值 1：suggestions | 建议参数（键与 GUI 控件/`Config` 字段同名） | `dict` | `gray_threshold` `min_area` `duplicate_distance` `verify_radius` `red_pixel_threshold` `red_ratio_threshold` `use_distance_center` `generate_grid` `grid_spacing` |
| `calibrate()` 返回值 2：diagnostics | 诊断数值（供日志/状态显示） | `dict` | `otsu` `dots` `blobs` `med_radius` `med_dot_area` `med_cell_area` `med_spacing` `med_target_gray` |
| 红点（dots）过滤 | 自动校准里认定为「已点击红点」的连通域 | `dict` | 面积 ≥ 8、宽高 ≤ 60、宽高比 0.4~2.5、填充率 ≥ 0.45 |
| 亮块（blobs）过滤 | 自动校准里认为是目标的连通域 | `dict` | 面积 ≥ 20、宽高均 ≥ 3 且 ≤ 2000 |

类不保存跨帧状态（去重由 `worker` 管），可被多线程各自实例化。

## 3. 输入/输出

- 输入：`detect(img, cfg)` 收 RGB ndarray（`capture.ScreenCapture.grab` 的输出）与 `Config` 实例；`calibrate(img)` 只收图像；`red_mask(img)` 只收图像。
- 输出：见上表，均为内存对象；**不读写任何文件**，不落盘截图。
- 关键算法口径：
  - 分割：`RGB→GRAY` → `GaussianBlur(3,3)` → 阈值 → `MORPH_OPEN`。固定阈值时用 `THRESH_BINARY`，`invert_bright=True` 改 `THRESH_BINARY_INV`；`use_otsu=True` 时用 OTSU（忽略 `gray_threshold`）。
  - 红色掩码：HSV 双区间 `H 0~10` 与 `H 170~180`（`S,V ≥ 70`）取并，再 `MORPH_OPEN`。
  - 单点模式（`generate_grid=False`）：每个亮块用 `_pick_center()` 取点击中心；`use_distance_center=True` 时用 `distanceTransform` 取轮廓内部最远点，否则用轮廓矩心、退化时用包围盒中心；随后 `_is_completed()` 判定是否已完成，完成则跳过。
  - 多点模式（`generate_grid=True`）：对每个亮块调 `_grid_points()`，`spacing=max(3, int(grid_spacing))`、起点 `half=spacing//2`、红点检查半径 `max(2, min(6, spacing//3))`；要求该网格点 `bright>0` 且其半径内**没有**红像素；累计到 `max_points` 立即停止。
  - 排序：按 `click_order`——`x_y` 排 `(x,y)`，`corner` 排 `x²+y²`，其余（含 `y_x`）排 `(y,x)`。
  - 完成判定 `_is_completed()` 三级优先：① 点击中心邻域（`r=max(3, min(10, verify_radius//2))`）红像素占比 > 0.4；② 存在面积 ≥ 8 的红色连通域，其质心落在轮廓内（`pointPolygonTest ≥ 0`）；③ 轮廓填充区内红像素均值/255 > `red_ratio_threshold`。
  - 自动校准阈值公式：`otsu=THRESH_OTSU` 阈值；`gray_threshold=clamp(med_target-15, 60, 250)`（无红点时 `clamp(otsu, 60, 250)`）；`min_area=clamp(med_cell*0.25, 10, 5000)`（无亮块时用 `med_blob*0.25`）；`duplicate_distance=clamp(med_spacing*0.6, 5, 100)` 否则 10；`verify_radius=clamp(med_radius*2+4, 8, 60)` 否则 12；`red_pixel_threshold=clamp(med_dot_area*0.4, 6, 500)` 否则 12；`red_ratio_threshold=round(min(0.60, max(0.05, med_dot_area/med_cell*0.6)), 3)` 否则 0.15；`grid_spacing=clamp(round(med_spacing), 3, 200)` 否则 20；`use_distance_center` 与 `generate_grid` 恒建议 True。
- 被谁使用：`worker.py`（`detect` / `red_mask`）、`main.py`（`calibrate`、预览用 `detect`）。

## 4. 【待确认】

- 多点模式**不做轮廓级完成判定**，只逐点检查「该点半径内是否有红像素」，因此密集红点可能被部分跳过；这是当前设计，未改。
- 多点模式下 `max_points` 截断发生在**亮块循环中途**，被截断的后续亮块不再处理；顺序取决于 `findContours` 的返回顺序（未排序），所以截断点在不同帧可能不同。
- 多点模式下候选点的 `area` 仍是**整个亮块**的面积，不是该网格点的面积；只有 `bbox` 是该亮块的外接矩形。
- `_is_completed` 会被 `red_ratio_threshold` 影响，而该校准结果依赖「抽样环带内没有红像素」的假设；目标紧邻时 `med_cell_area` 可能偏大。
- 自动校准只分析**一帧**，若该帧恰好都是未点击目标（无红点），红色相关参数保持默认。
