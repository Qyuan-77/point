"""全局参数配置（可通过 GUI 调整，也可直接改这里做默认值）。"""

from dataclasses import dataclass


@dataclass
class Config:
    # 检测区域（屏幕物理像素，left, top, width, height）
    region: tuple = (0, 0, 1920, 1080)

    # ---- 灰度分割 ----
    gray_threshold: int = 180        # 灰度阈值（bar 0~255）
    invert_bright: bool = False      # True 表示检测暗色目标
    use_otsu: bool = False           # True 表示使用 OTSU 自动阈值

    # ---- 目标过滤 ----
    min_area: int = 50               # 最小目标面积（像素）
    duplicate_distance: int = 15     # 与已点击点距离小于该值视为重复
    click_order: str = "y_x"         # 点击顺序: y_x=从上到下/从左到右, x_y=从左到右/从上到下, corner=距左上角由近到远
    generate_grid: bool = True       # True: 在白色区域内按等距行列生成多个点击点
    grid_spacing: int = 20           # 点阵间距（px），可用自动校准从红点间距推断
    max_points: int = 800            # 单帧最多生成的点数（防溢出）
    use_distance_center: bool = True # 用距离变换取目标内部最远点作为点击中心

    # ---- 点击与验证 ----
    click_interval: float = 0.15     # 相邻点击最小间隔（秒）
    verify_delay: float = 0.25       # 点击后等待变红的时间（秒）
    max_retries: int = 3             # 点击后无红色反馈的最大重试次数
    red_pixel_threshold: int = 12    # 点击点周围红像素数 >= 该值判定成功
    verify_radius: int = 12          # 验证区域半径（像素）

    # ---- 自动模式（一次性截图）----
    auto_mode: bool = False          # True: 只截一次图，点完该帧全部目标后按翻页键并结束
    page_direction: str = "down"     # 自动模式结束时的翻页键: down=PageDown, up=PageUp

    # ---- 红色完成态排除 ----
    red_ratio_threshold: float = 0.15  # 轮廓框内红色占比超过该值视为已完成

    # ---- 循环 ----
    scan_interval: float = 0.2       # 无目标时的轮询间隔（秒）
    auto_stop: bool = True           # 全部完成后自动停止