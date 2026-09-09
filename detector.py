"""目标检测：灰度阈值分割 + 连通域 + 红色完成态排除。"""

import cv2
import numpy as np


class Detector:
    """纯函数式检测器，不保存跨帧状态（去重状态由 worker 管理）。

    detect() 返回 (candidates, bright_mask, red_mask)，
    其中 candidates 的坐标为检测区域内的局部坐标。
    """

    def __init__(self) -> None:
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    # ---------------- 公开接口 ----------------
    def detect(self, img, cfg):
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        bright = self._bright_mask(gray, cfg)
        bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, self._kernel)

        red = self._red_mask(img)

        if cfg.use_distance_center:
            dist = cv2.distanceTransform(bright // 255, cv2.DIST_L2, 5)
        else:
            dist = None

        contours, _ = cv2.findContours(
            bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        n_red, _, red_stats, red_cents = cv2.connectedComponentsWithStats(red, 8)

        candidates = []
        use_grid = getattr(cfg, "generate_grid", False)
        for c in contours:
            area = cv2.contourArea(c)
            if area < cfg.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if use_grid:
                pts = self._grid_points(bright, red, x, y, w, h, cfg)
                for px, py in pts:
                    candidates.append(
                        {"x": px, "y": py, "area": area, "bbox": (x, y, w, h)}
                    )
                    if len(candidates) >= cfg.max_points:
                        break
                if len(candidates) >= cfg.max_points:
                    break
            else:
                cx, cy = self._pick_center(bright, dist, c, cfg)
                if self._is_completed(red, c, (cx, cy), cfg, red_stats, red_cents):
                    continue
                candidates.append(
                    {"x": cx, "y": cy, "area": area, "bbox": (x, y, w, h)}
                )

        order = getattr(cfg, "click_order", "y_x")
        if order == "x_y":
            candidates.sort(key=lambda p: (p["x"], p["y"]))
        elif order == "corner":
            candidates.sort(key=lambda p: (p["x"] ** 2 + p["y"] ** 2))
        else:
            # 从上到下、从左到右，保证点击顺序稳定
            candidates.sort(key=lambda p: (p["y"], p["x"]))
        return candidates, bright, red

    def red_mask(self, img) -> np.ndarray:
        return self._red_mask(img)

    def calibrate(self, img):
        """Analyze a single frame and suggest parameters.

        Returns (suggestions, diagnostics). Suggestions map directly to GUI
        controls; diagnostics are for the log/status display.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        red = self._red_mask(img)

        otsu = int(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])

        bright = ((gray > max(40, otsu)).astype(np.uint8)) * 255
        bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, self._kernel)
        n_labels, labels, stats, cents = cv2.connectedComponentsWithStats(bright, 8)
        blobs = []
        for i in range(1, n_labels):
            x, y, w, h, a = stats[i]
            if a < 20 or w < 3 or h < 3 or w > 2000 or h > 2000:
                continue
            blobs.append({"area": a, "cx": int(cents[i][0]), "cy": int(cents[i][1])})

        n_red, _, rstats, rcents = cv2.connectedComponentsWithStats(red, 8)
        dots = []
        for i in range(1, n_red):
            x, y, w, h, a = rstats[i]
            if a < 8 or w > 60 or h > 60:
                continue
            if w / float(max(1, h)) < 0.4 or w / float(max(1, h)) > 2.5:
                continue
            if a / (w * h) < 0.45:
                continue
            dots.append({"area": a, "cx": int(rcents[i][0]), "cy": int(rcents[i][1])})

        cell_areas, target_grays = [], []
        for d in dots:
            cy, cx = d["cy"], d["cx"]
            r = float(np.sqrt(d["area"] / np.pi))
            cand_labels = set()
            for oy, ox in [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r)]:
                yy = cy + int(round(oy))
                xx = cx + int(round(ox))
                if 0 <= yy < gray.shape[0] and 0 <= xx < gray.shape[1]:
                    l = labels[yy, xx]
                    if l > 0:
                        cand_labels.add(int(l))
            if cand_labels:
                best = max(cand_labels, key=lambda l: stats[l][4])
                cell_areas.append(float(stats[best][4]))
            r = float(np.sqrt(d["area"] / np.pi))
            yy, xx = np.ogrid[: gray.shape[0], : gray.shape[1]]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            ann = (dist >= r + 3) & (dist <= r + 12)
            vals = gray[ann & (red == 0)]
            if vals.size:
                target_grays.append(float(np.median(vals)))

        spacings = []
        if len(dots) >= 2:
            pts = np.array([[d["cx"], d["cy"]] for d in dots], dtype=float)
            for i, p in enumerate(pts):
                d2 = np.sum((pts - p) ** 2, axis=1)
                d2[i] = 1e18
                spacings.append(float(np.sqrt(d2.min())))

        med_radius = float(np.median([np.sqrt(d["area"] / np.pi) for d in dots])) if dots else 0.0
        med_dot_area = float(np.median([d["area"] for d in dots])) if dots else 0.0
        med_cell = float(np.median(cell_areas)) if cell_areas else 0.0
        med_blob = float(np.median([b["area"] for b in blobs])) if blobs else 0.0
        med_spacing = float(np.median(spacings)) if spacings else 0.0
        med_target = float(np.median(target_grays)) if target_grays else 0.0

        def clamp(v, lo, hi):
            return int(max(lo, min(hi, v)))

        if dots and med_target > 0:
            gray_threshold = clamp(med_target - 15, 60, 250)
        else:
            gray_threshold = clamp(otsu, 60, 250)
        min_area = clamp(med_cell * 0.25, 10, 5000) if med_cell > 0 else clamp(med_blob * 0.25, 10, 5000)
        duplicate_distance = clamp(med_spacing * 0.6, 5, 100) if med_spacing > 0 else 10
        verify_radius = clamp(med_radius * 2 + 4, 8, 60) if med_radius > 0 else 12
        red_pixel_threshold = clamp(med_dot_area * 0.4, 6, 500) if med_dot_area > 0 else 12
        if med_cell > 0 and med_dot_area > 0:
            red_ratio_threshold = round(min(0.60, max(0.05, (med_dot_area / med_cell) * 0.6)), 3)
        else:
            red_ratio_threshold = 0.15

        grid_spacing = clamp(round(med_spacing), 3, 200) if med_spacing > 0 else 20
        suggestions = {
            "gray_threshold": gray_threshold,
            "min_area": min_area,
            "duplicate_distance": duplicate_distance,
            "verify_radius": verify_radius,
            "red_pixel_threshold": red_pixel_threshold,
            "red_ratio_threshold": red_ratio_threshold,
            "use_distance_center": True,
            "generate_grid": True,
            "grid_spacing": grid_spacing,
        }
        diagnostics = {
            "otsu": otsu,
            "dots": len(dots),
            "blobs": len(blobs),
            "med_radius": med_radius,
            "med_dot_area": med_dot_area,
            "med_cell_area": med_cell,
            "med_spacing": med_spacing,
            "med_target_gray": med_target,
        }
        return suggestions, diagnostics
    # ---------------- 内部实现 ----------------
    @staticmethod
    def _bright_mask(gray, cfg) -> np.ndarray:
        if cfg.use_otsu:
            _, mask = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            return mask
        flag = cv2.THRESH_BINARY_INV if cfg.invert_bright else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, cfg.gray_threshold, 255, flag)
        return mask

    @staticmethod
    def _red_mask(img) -> np.ndarray:
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        lower1 = np.array([0, 70, 70], dtype=np.uint8)
        upper1 = np.array([10, 255, 255], dtype=np.uint8)
        lower2 = np.array([170, 70, 70], dtype=np.uint8)
        upper2 = np.array([180, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    @staticmethod
    def _grid_points(bright, red, x, y, w, h, cfg):
        """在白色区域内按等距行列生成点击点，跳过已变红的位置。"""
        spacing = max(3, int(cfg.grid_spacing))
        half = spacing // 2
        radius = max(2, min(6, spacing // 3))
        points = []
        gy = y + half
        while gy < y + h:
            gx = x + half
            while gx < x + w:
                if bright[gy, gx] > 0 and not Detector._point_has_red(red, gx, gy, radius):
                    points.append((gx, gy))
                gx += spacing
            gy += spacing
        return points

    @staticmethod
    def _point_has_red(red, x, y, radius) -> bool:
        r = int(radius)
        y0 = max(0, y - r); y1 = min(red.shape[0], y + r + 1)
        x0 = max(0, x - r); x1 = min(red.shape[1], x + r + 1)
        roi = red[y0:y1, x0:x1]
        return bool(roi.size) and bool((roi > 0).any())

    @staticmethod
    def _is_completed(red, contour, center, cfg, red_stats, red_cents) -> bool:
        """判断目标是否已完成。

        优先级：
        1) 点击中心邻域已变红；
        2) 目标轮廓内存在红色连通域（红点/标记落在目标内部）；
        3) 目标轮廓内红像素占比超过阈值（兜底）。
        """
        cy, cx = center
        r = int(max(3, min(10, cfg.verify_radius // 2)))
        y0 = max(0, cy - r); y1 = min(red.shape[0], cy + r + 1)
        x0 = max(0, cx - r); x1 = min(red.shape[1], cx + r + 1)
        roi = red[y0:y1, x0:x1]
        if roi.size and float((roi > 0).mean()) > 0.4:
            return True
        for i in range(1, len(red_stats)):
            if red_stats[i][4] < 8:
                continue
            px, py = red_cents[i]
            if cv2.pointPolygonTest(contour, (float(px), float(py)), False) >= 0:
                return True
        fill = np.zeros(red.shape, dtype=np.uint8)
        cv2.drawContours(fill, [contour], -1, 255, -1)
        mask = fill > 0
        if mask.any():
            ratio = float(red[mask].mean()) / 255.0
            if ratio > cfg.red_ratio_threshold:
                return True
        return False

    @staticmethod
    def _pick_center(bright, dist, contour, cfg):
        x, y, w, h = cv2.boundingRect(contour)
        if dist is not None and w >= 3 and h >= 3:
            # 在目标内部取离边缘最远的点，避免点击到边缘
            fill = np.zeros(bright.shape, dtype=np.uint8)
            cv2.drawContours(fill, [contour], -1, 255, -1)
            roi = fill[y : y + h, x : x + w]
            d = dist[y : y + h, x : x + w] * (roi > 0)
            idx = np.unravel_index(np.argmax(d), d.shape)
            return x + int(idx[1]), y + int(idx[0])
        M = cv2.moments(contour)
        if M["m00"] > 0:
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
        return x + w // 2, y + h // 2