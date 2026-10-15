"""worker_logic_probe: 用假的截图/检测/键鼠替换真实副作用，验证两种运行模式与暂停逻辑。

**不点击真实鼠标、不按真实按键**：worker 模块里的 pyautogui / ScreenCapture / Detector 全部被替身顶掉。
可随时重跑（改 worker.py 或 config.py 后先跑它）。
运行：
    $env:PYTHONIOENCODING='utf-8'
    & 'E:\\anconda\\envs\\point_clicker\\python.exe' worker_logic_probe.py
"""

import os
import sys
import threading
import time

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

import worker as W  # noqa: E402
from config import Config  # noqa: E402

# ---------------- 假替身 ----------------
events = []


class FakePyAutoGUI:
    class FailSafeException(Exception):
        pass

    @staticmethod
    def click(x, y):
        events.append(("click", int(x), int(y)))

    @staticmethod
    def press(key):
        events.append(("press", str(key)))


class FakeCapture:
    def __init__(self):
        self.grabs = []

    def grab(self, region):
        self.grabs.append(tuple(region))
        return np.zeros((max(1, region[3]), max(1, region[2]), 3), dtype=np.uint8)

    def close(self):
        pass


class FakeDetector:
    """detect() 按 frames 队列依次返回；red_mask() 按 red_seq 依次返回红/不红。"""

    def __init__(self):
        self.frames = []
        self.red_seq = []
        self.red_calls = 0

    def detect(self, img, cfg):
        frame = self.frames.pop(0) if self.frames else []
        return frame, None, None

    def red_mask(self, img):
        self.red_calls += 1
        if self.red_seq:
            val = self.red_seq.pop(0)
        else:
            val = 255
        h, w = img.shape[:2]
        return np.full((h, w), val, dtype=np.uint8)


W.pyautogui = FakePyAutoGUI

results = []


def chk(name, cond, extra=""):
    results.append((name, bool(cond), extra))


def make_worker(cands_frames, red_seq, **cfg_kw):
    W.ScreenCapture = FakeCapture
    W.Detector = FakeDetector
    cfg = Config(
        region=(100, 200, 300, 200),
        click_interval=0.01,
        verify_delay=0.01,
        duplicate_distance=0,   # 关掉跨帧去重，便于断言
        **cfg_kw
    )
    w = W.ClickWorker(cfg)
    w._detector.frames = list(cands_frames)
    w._detector.red_seq = list(red_seq)
    return w


def cand(x, y):
    return {"x": x, "y": y, "bbox": (x - 3, y - 3, 6, 6)}


# ---- 1. 自动模式：3 个目标，点完按 PageDown ----
events.clear()
w = make_worker([[cand(10, 10), cand(50, 30), cand(20, 80)]], [], auto_mode=True, page_direction="down")
logs = []
w.log.connect(logs.append)
clicked, failed = w._run_auto_once()
clicks = [e for e in events if e[0] == "click"]
presses = [e for e in events if e[0] == "press"]
chk("自动模式：3 次点击", len(clicks) == 3, clicks)
chk("自动模式：坐标加区域偏移且保持顺序",
    clicks == [("click", 110, 210), ("click", 150, 230), ("click", 120, 280)], clicks)
chk("自动模式：按一次 pagedown", presses == [("press", "pagedown")], presses)
chk("自动模式：计数正确", (clicked, failed) == (3, 0), (clicked, failed))
chk("自动模式：全区域只截一次图",
    len([g for g in w._capture.grabs if g == (100, 200, 300, 200)]) == 1, w._capture.grabs[:2])
chk("验证窗口 = (sx-r, sy-r, 2r, 2r)，r=verify_radius",
    w._capture.grabs[1] == (110 - 12, 210 - 12, 24, 24), w._capture.grabs[1])
chk("自动模式：日志含按键提示", any("PageDown" in s for s in logs), logs[-1:])

# ---- 2. 自动模式：方向=上 → 按 PageUp ----
events.clear()
w = make_worker([[cand(10, 10)]], [], auto_mode=True, page_direction="up")
w._run_auto_once()
presses = [e for e in events if e[0] == "press"]
chk("自动模式：方向=上按 pageup", presses == [("press", "pageup")], presses)

# ---- 3. 自动模式：0 个目标 → 不按键 ----
events.clear()
w = make_worker([[]], [], auto_mode=True, page_direction="down")
logs = []
w.log.connect(logs.append)
clicked, failed = w._run_auto_once()
chk("自动模式：0 目标时不按键", [e for e in events if e[0] == "press"] == [], events)
chk("自动模式：0 目标时计数为 0", (clicked, failed) == (0, 0), (clicked, failed))
chk("自动模式：0 目标时给出说明", any("没有识别到目标" in s for s in logs), logs)

# ---- 4. 重试逻辑：第 1 次没变红，第 2 次变红 ----
events.clear()
w = make_worker([[cand(1, 1)]], [0, 255], auto_mode=True, page_direction="down", max_retries=3)
logs = []
w.log.connect(logs.append)
clicked, failed = w._run_auto_once()
chk("重试后判成功", (clicked, failed) == (1, 0), (clicked, failed))
chk("重试：点了 2 次", len([e for e in events if e[0] == "click"]) == 2, events)
chk("重试：日志含重试提示", any("准备重试" in s for s in logs), logs)

# ---- 5. 失败：一直不红 → 计入失败 ----
events.clear()
w = make_worker([[cand(1, 1)]], [0, 0, 0, 0, 0], auto_mode=True, page_direction="down", max_retries=1)
clicked, failed = w._run_auto_once()
chk("始终不红：判失败", (clicked, failed) == (0, 1), (clicked, failed))
chk("始终不红：按 max_retries+1 次点击",
    len([e for e in events if e[0] == "click"]) == 2,
    [e for e in events if e[0] == "click"])
chk("始终不红：仍按一次翻页键", [e for e in events if e[0] == "press"] == [("press", "pagedown")], events)

# ---- 6. 循环模式：第 1 帧有目标，第 2 帧空 → 自动停止 ----
events.clear()
w = make_worker([[cand(5, 5)], []], [], auto_mode=False, auto_stop=True)
logs = []
w.log.connect(logs.append)
clicked, failed = w._run_loop()
chk("循环模式：点 1 次后停止", (clicked, failed) == (1, 0), (clicked, failed))
chk("循环模式：未按翻页键", [e for e in events if e[0] == "press"] == [], events)
chk("循环模式：日志提示自动停止", any("自动停止" in s for s in logs), logs[-1:])

# ---- 7. 暂停：暂停期间不点击，恢复后继续 ----
events.clear()
w = make_worker([[cand(1, 1), cand(2, 2)]], [], auto_mode=True, page_direction="down")
w._paused = True
done = {}

t = threading.Thread(target=lambda: done.update(zip(("c", "f"), w._run_auto_once())))
t.start()
time.sleep(0.35)
chk("暂停期间没有点击", [e for e in events if e[0] == "click"] == [], events)
chk("暂停期间也没有按键", [e for e in events if e[0] == "press"] == [], events)
chk("暂停状态可读", w.is_paused is True)
w.toggle_pause()                     # 恢复
t.join(timeout=5)
chk("恢复后全部点完", len([e for e in events if e[0] == "click"]) == 2, events)
chk("恢复后仍按键一次", [e for e in events if e[0] == "press"] == [("press", "pagedown")], events)
chk("暂停信号往返", w.is_paused is False)

# ---- 8. stop() 立即中断 ----
events.clear()
w = make_worker([[cand(1, 1), cand(2, 2), cand(3, 3)]], [], auto_mode=True, page_direction="down")
stop_done = {}


def run_and_stop():
    stop_done["r"] = w._run_auto_once()


t = threading.Thread(target=run_and_stop)
t.start()
time.sleep(0.05)
w.stop()
t.join(timeout=5)
chk("stop 后不再全部点完", len([e for e in events if e[0] == "click"]) < 3, events)
chk("stop 后不按翻页键", [e for e in events if e[0] == "press"] == [], events)

ok = True
for name, res, extra in results:
    print(("PASS " if res else "FAIL "), name, extra)
    ok = ok and res
print("RESULT", "ALL_PASS" if ok else "HAS_FAILURE")
