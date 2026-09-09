"""后台自动点击线程：循环截图 → 检测 → 点击 → 红色验证。"""

import time

import cv2
import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal

from capture import ScreenCapture
from detector import Detector


class ClickWorker(QThread):
    frame_ready = pyqtSignal(object)    # 预览图（RGB ndarray，已画标记）
    log = pyqtSignal(str)
    stats = pyqtSignal(int, int, int)   # 剩余目标数, 已点击数, 失败数
    finished_ok = pyqtSignal(int, int)  # 已点击数, 失败数

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._running = True
        self._capture = ScreenCapture()
        self._detector = Detector()
        self._clicked = []      # 已成功点击的点（局部坐标），近距去重兜底
        self._last_state = None

    def stop(self):
        """请求停止，线程在下一个安全点退出。"""
        self._running = False

    # ---------------- 主循环 ----------------
    def run(self):
        clicked = 0
        failed = 0
        ever_worked = False
        try:
            while self._running:
                try:
                    img = self._capture.grab(self.cfg.region)
                    candidates, _, _ = self._detector.detect(img, self.cfg)
                except Exception as exc:
                    self._log(f"检测异常：{exc}")
                    self._sleep(0.5)
                    continue

                fresh = self._filter_duplicates(candidates)
                self.frame_ready.emit(self._draw_preview(img, fresh))
                self.stats.emit(len(fresh), clicked, failed)

                if not fresh:
                    self._mark_state("idle")
                    if ever_worked and self.cfg.auto_stop:
                        self._log("未检测到剩余目标，自动停止。")
                        break
                    self._sleep(self.cfg.scan_interval)
                    continue

                ever_worked = True
                self._mark_state("busy")
                # 一帧内按顺序点击该帧识别出的所有目标；
                # 点完当前帧全部目标后，重新截图进入下一步。
                remaining_in_frame = len(fresh)
                for c in fresh:
                    if not self._running:
                        break
                    sx = self.cfg.region[0] + c["x"]
                    sy = self.cfg.region[1] + c["y"]
                    if self._click_and_verify(sx, sy):
                        clicked += 1
                        self._clicked.append((c["x"], c["y"]))
                        if len(self._clicked) > 200:
                            self._clicked = self._clicked[-200:]
                        self._log(f"点击成功 ({sx}, {sy})")
                    else:
                        failed += 1
                        self._log(f"点击失败（多次重试后仍无红色反馈）({sx}, {sy})")
                    remaining_in_frame -= 1
                    self.stats.emit(remaining_in_frame, clicked, failed)
                    if self._running:
                        self._sleep(self.cfg.click_interval)
        except pyautogui.FailSafeException:
            self._log("触发 PyAutoGUI 紧急停止（鼠标已移到屏幕左上角）。")
        except Exception as exc:
            self._log(f"线程异常：{exc}")
        finally:
            self._log(f"线程结束：已点击 {clicked}，失败 {failed}")
            self.finished_ok.emit(clicked, failed)

    # ---------------- 点击与验证 ----------------
    def _click_and_verify(self, sx, sy) -> bool:
        """点击并等待红色反馈；返回是否成功。"""
        for attempt in range(1, self.cfg.max_retries + 2):
            if not self._running:
                return False
            pyautogui.click(sx, sy)
            if self._running:
                self._sleep(self.cfg.verify_delay)
            red_count = self._count_red_near(sx, sy)
            if red_count >= self.cfg.red_pixel_threshold:
                return True
            if attempt <= self.cfg.max_retries:
                self._log(f"第 {attempt} 次点击后红色像素仅 {red_count} 个，准备重试…")
        return False

    def _count_red_near(self, sx, sy) -> int:
        r = int(self.cfg.verify_radius)
        left = max(0, sx - r)
        top = max(0, sy - r)
        img = self._capture.grab((left, top, 2 * r, 2 * r))
        red = self._detector.red_mask(img)
        return int((red > 0).sum())

    # ---------------- 辅助 ----------------
    def _filter_duplicates(self, candidates):
        if not self._clicked:
            return candidates
        d2 = self.cfg.duplicate_distance ** 2
        fresh = []
        for c in candidates:
            dup = any(
                (c["x"] - px) ** 2 + (c["y"] - py) ** 2 < d2
                for px, py in self._clicked
            )
            if not dup:
                fresh.append(c)
        return fresh

    @staticmethod
    def _draw_preview(img, candidates):
        display = img.copy()
        for i, c in enumerate(candidates, 1):
            x, y, w, h = c["bbox"]
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 1)
            cv2.drawMarker(
                display, (c["x"], c["y"]), (0, 0, 255), cv2.MARKER_CROSS, 16, 2
            )
            cv2.putText(
                display,
                str(i),
                (x, max(0, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
                cv2.LINE_AA,
            )
        return display

    def _mark_state(self, state):
        if state == self._last_state:
            return
        self._last_state = state
        if state == "idle":
            self._log("未发现目标，持续扫描中…")
        elif state == "busy":
            self._log("发现目标，开始点击…")

    def _log(self, text):
        self.log.emit(text)

    @staticmethod
    def _sleep(seconds):
        time.sleep(max(0.0, seconds))