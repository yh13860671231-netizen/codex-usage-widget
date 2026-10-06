# -*- coding: utf-8 -*-
"""Codex + ZCode 用量桌面悬浮窗

双数据源（Codex session 快照 / ZCode 日志额度快照），圆角深色卡片置顶显示。
两种形态：完整卡片（时钟 + 分组限额 + 上下文）/ 顶部迷你条（时钟 + 关键剩余%），
点"—"最小化成迷你条，点迷你条弹回卡片，位置分别记忆。
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime

SESSIONS_DIR = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
ZCODE_LOG_DIR = os.path.join(os.path.expanduser("~"), ".zcode", "v2", "logs")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget_config.json")
REFRESH_MS = 30_000
TAIL_BYTES = 262144
ENABLE_ACRYLIC = False  # 实测 DWM backdrop 对无框挖洞窗口无效，默认关闭

CODEX_EXES = (
    # npm 原生 exe（本机）
    r"D:\dev\nodejs\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64"
    r"\vendor\x86_64-pc-windows-msvc\bin\codex.exe",
    # 通用：PATH 里的 codex（Windows 需 .cmd/.exe 解析）
    "codex",
)

# ---- 设计 tokens（Tokyo Night 系深色）----
TRANSPARENT = "#a040ff"  # 窗口挖洞色，内容中不会出现
CARD = "#16161e"         # 卡片底
INK = "#e2e8f0"          # 主文字
SUB = "#8b93a7"          # 次级文字
FAINT = "#5b6172"        # 弱文字 / 页脚
ACCENT = "#7aa2f7"       # 标题蓝
CLOCK = "#c8d3f5"        # 时钟
TRACK = "#26262f"        # 进度条底槽
LINE = "#2a2a35"         # 分隔线
GOOD, WARN, BAD = "#9ece6a", "#e0af68", "#f7768e"

W, H = 264, 288          # 完整卡片
W_MINI, H_MINI = 320, 46  # 顶部迷你条
PAD = 16
FONT = "Microsoft YaHei UI"
BAR_H = 7

# 纵向布局（create_text/capsule 的 y 坐标）
Y_TITLE, Y_CLOCK = 17, 54
Y_G1 = 78
Y_B1, Y_BAR1, Y_S1 = 94, 106, 128
Y_B2, Y_BAR2, Y_S2 = 146, 158, 180
Y_G2 = 202
Y_Z1, Y_ZBAR, Y_ZSUB = 218, 230, 252
Y_LINE, Y_FOOT = 264, 274


def latest_session_file():
    files = glob.glob(os.path.join(SESSIONS_DIR, "**", "*.jsonl"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found is not None:
                return found
    return None


def load_usage():
    """返回 (rate_limits, token_usage, context_window, line_timestamp) 或 None。"""
    path = latest_session_file()
    if not path:
        return None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        text = f.read().decode("utf-8", "ignore")
    for line in reversed(text.splitlines()):
        if '"rate_limits"' not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        rl = find_key(obj, "rate_limits")
        if rl and isinstance(rl.get("primary"), dict):
            return rl, find_key(obj, "last_token_usage"), find_key(obj, "model_context_window"), obj.get("timestamp")
    return None


def load_live_rate_limits():
    """启动 codex app-server 询问官方实时限额（与 /usage、官方 UI 同源）。

    返回 dict(primary={used_percent, resets_at}, secondary=...) 或 None。
    耗时约 2-4 秒（进程冷启），必须在后台线程调用。
    """
    for exe in CODEX_EXES:
        try:
            proc = subprocess.Popen(
                [exe, "app-server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
        except OSError:
            continue
        responses = {}

        def reader(p=proc):
            for line in p.stdout:
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if "id" in obj:
                    responses[obj["id"]] = obj

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        def send(obj):
            try:
                proc.stdin.write((json.dumps(obj) + "\n").encode())
                proc.stdin.flush()
            except OSError:
                pass

        def wait(rid, timeout=8):
            deadline = time.time() + timeout
            while time.time() < deadline and rid not in responses:
                time.sleep(0.05)
            return responses.get(rid)

        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "codex-usage-widget", "title": "Usage Widget",
                               "version": "1.0"}}})
            if wait(1):
                send({"jsonrpc": "2.0", "method": "initialized"})
                time.sleep(0.4)
                send({"jsonrpc": "2.0", "id": 2,
                      "method": "account/rateLimits/read", "params": {}})
                r = wait(2)
                if r and "result" in r:
                    rl = (r["result"].get("rateLimits")
                          or r["result"].get("rateLimitsByLimitId", {}).get("codex"))
                    if rl and "primary" in rl:
                        return {
                            "primary": {
                                "used_percent": rl["primary"].get("usedPercent"),
                                "resets_at": rl["primary"].get("resetsAt"),
                            },
                            "secondary": {
                                "used_percent": rl["secondary"].get("usedPercent"),
                                "resets_at": rl["secondary"].get("resetsAt"),
                            } if rl.get("secondary") else None,
                            "live": True,
                        }
        finally:
            try:
                proc.kill()
            except OSError:
                pass
    return None


def load_zcode_usage():
    """读 ZCode 日志的最新额度快照（当日 token 池）。

    返回 dict(total, remaining, period_end) 或 None。
    """
    today = time.strftime("%Y-%m-%d")
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    for day in (today, yesterday):
        path = os.path.join(ZCODE_LOG_DIR, f"{day}.log")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            text = f.read().decode("utf-8", "ignore")
        for line in reversed(text.splitlines()):
            if '"remaining_units"' not in line:
                continue
            brace = line.find("{")
            if brace < 0:
                continue
            try:
                obj = json.loads(line[brace:])
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload")
            data = payload.get("data") if isinstance(payload, dict) else None
            balances = (data.get("balances") if isinstance(data, dict) else None) \
                or find_key(obj, "balances")
            if isinstance(balances, list) and balances:
                b = balances[0]
                total = b.get("total_units") or 0
                remaining = b.get("remaining_units") or 0
                if total > 0 and day == today:
                    return {"total": total, "remaining": remaining,
                            "period_end": b.get("period_end")}
        break
    return None


def level_color(remain_pct):
    """剩余视角：剩得多绿，剩 <20% 红。"""
    return GOOD if remain_pct > 40 else WARN if remain_pct > 20 else BAD


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            return cfg
    except (OSError, ValueError):
        pass
    return {}


def save_config(**kv):
    cfg = load_config()
    cfg.update(kv)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


def capsule_pts(x1, y1, x2, y2, r):
    """smooth polygon 近似圆角矩形的点集。"""
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def fmt_countdown(resets_at):
    remain = resets_at - time.time()
    if remain <= 0:
        return "已重置"
    h, m = int(remain // 3600), int(remain % 3600 // 60)
    return f"{h} 小时 {m} 分后重置" if h else f"{m} 分后重置"


class UsageWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.root.configure(bg=TRANSPARENT)
        self.mode = "card"

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        # 交互：拖动 / 右键
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.canvas.bind("<Button-3>", self.show_menu)

        self.build_card()
        self.tick()
        self.refresh()
        self.keep_on_top()
        self.root.mainloop()

    # ---------- 形态构建 ----------

    def build_card(self):
        cfg = load_config()
        x, y = cfg.get("x", 60), cfg.get("y", 60)
        self.clear_bg = cfg.get("bg") == "clear"
        self.mode = "card"
        self.canvas.delete("all")
        self.canvas.config(width=W, height=H)
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        bg_fill = TRANSPARENT if self.clear_bg else CARD
        self.capsule(1, 1, W - 1, H - 1, 14, fill=bg_fill,
                     outline=LINE if self.clear_bg else "")

        # 头部：标题 + 三按钮（图钉/最小化/关闭，hover 展开功能文字）
        self.canvas.create_text(PAD, Y_TITLE, anchor="w", text="⚡ 用量监控",
                                fill=ACCENT, font=(FONT, 9, "bold"))
        right = W - PAD - 2
        self.pinned = bool(cfg.get("pinned"))
        self.btns = {}
        clicks = {"pin": self.toggle_pin, "min": self.build_mini,
                  "close": self.root.destroy}
        for key, x_sym in (("pin", right - 44), ("min", right - 26), ("close", right - 8)):
            meta = self._btn_meta(key)
            bg = self.canvas.create_polygon(
                capsule_pts(x_sym - 8, Y_TITLE - 8, x_sym + 8, Y_TITLE + 8, 8),
                smooth=True, fill=bg_fill, outline=FAINT, tags=f"btn-{key}")
            sym = self.canvas.create_text(
                x_sym, Y_TITLE, text=meta["sym"], fill=meta["sym_fill"],
                font=(FONT, 8), tags=f"btn-{key}")
            txt = self.canvas.create_text(
                x_sym - 18, Y_TITLE, anchor="e", text=meta["txt"], fill=INK,
                font=(FONT, 8), state="hidden", tags=f"btn-{key}")
            self.canvas.tag_bind(f"btn-{key}", "<Enter>",
                                 lambda e, k=key: self.on_btn_enter(k))
            self.canvas.tag_bind(f"btn-{key}", "<Leave>",
                                 lambda e, k=key: self.on_btn_leave(k))
            self.canvas.tag_bind(f"btn-{key}", "<Button-1>",
                                 lambda e, k=key: clicks[k]())
            self.btns[key] = {"bg": bg, "sym": sym, "txt": txt, "w": 16, "x": x_sym}

        # 时钟
        self.clock_id = self.canvas.create_text(
            W / 2, Y_CLOCK, text="00:00:00", fill=CLOCK, font=(FONT, 22, "bold"))

        # 分组标签
        self.canvas.create_text(PAD, Y_G1, anchor="w", text="CODEX",
                                fill=FAINT, font=(FONT, 7, "bold"))

        # 限额块 × 2
        self.b1_label = self.canvas.create_text(PAD, Y_B1, anchor="w",
                                                text="5 小时窗口", fill=SUB, font=(FONT, 9))
        self.b1_value = self.canvas.create_text(W - PAD, Y_B1, anchor="e",
                                                text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.capsule(PAD, Y_BAR1, W - PAD, Y_BAR1 + BAR_H, BAR_H / 2, fill=TRACK, outline="")
        self.b1_fill = None
        self.b1_sub = self.canvas.create_text(W - PAD, Y_S1, anchor="e",
                                              text="", fill=SUB, font=(FONT, 9))

        self.b2_label = self.canvas.create_text(PAD, Y_B2, anchor="w",
                                                text="本周额度", fill=SUB, font=(FONT, 9))
        self.b2_value = self.canvas.create_text(W - PAD, Y_B2, anchor="e",
                                                text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.capsule(PAD, Y_BAR2, W - PAD, Y_BAR2 + BAR_H, BAR_H / 2, fill=TRACK, outline="")
        self.b2_fill = None
        self.b2_sub = self.canvas.create_text(W - PAD, Y_S2, anchor="e",
                                              text="", fill=SUB, font=(FONT, 9))

        # ZCode 区块
        self.canvas.create_text(PAD, Y_G2, anchor="w", text="ZCODE",
                                fill=FAINT, font=(FONT, 7, "bold"))
        self.z_label = self.canvas.create_text(PAD, Y_Z1, anchor="w",
                                               text="今日额度", fill=SUB, font=(FONT, 9))
        self.z_value = self.canvas.create_text(W - PAD, Y_Z1, anchor="e",
                                               text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.capsule(PAD, Y_ZBAR, W - PAD, Y_ZBAR + BAR_H, BAR_H / 2, fill=TRACK, outline="")
        self.z_fill = None
        self.z_sub = self.canvas.create_text(W - PAD, Y_ZSUB, anchor="e",
                                             text="", fill=SUB, font=(FONT, 9))

        # 页脚
        self.canvas.create_line(PAD, Y_LINE, W - PAD, Y_LINE, fill=LINE)
        self.foot_id = self.canvas.create_text(W / 2, Y_FOOT, text="",
                                               fill=FAINT, font=(FONT, 8))

        self.menu.delete(0, "end")
        if not hasattr(self, "pin_var"):
            self.pin_var = tk.BooleanVar(value=self.pinned)
        else:
            self.pin_var.set(self.pinned)
        self.menu.add_checkbutton(label="固定位置（固定后不可拖动）",
                                  variable=self.pin_var, command=self.on_pin_menu)
        self.menu.add_command(label="背景：切换为透明" if not self.clear_bg else "背景：切换为实心",
                              command=self.toggle_bg)
        self.menu.add_command(label="最小化到顶部", command=self.build_mini)
        self.menu.add_command(label="立即刷新", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)

    def build_mini(self):
        cfg = load_config()
        mini_x = cfg.get("mini_x")
        if mini_x is None:
            mini_x = (self.root.winfo_screenwidth() - W_MINI) // 2
        if self.mode != "mini":  # 仅从卡片最小化时记卡片位置，重建迷你条时不覆盖
            save_config(x=self.root.winfo_x(), y=self.root.winfo_y())
        self.clear_bg = cfg.get("bg") == "clear"
        self.mode = "mini"
        self.canvas.delete("all")
        self.canvas.config(width=W_MINI, height=H_MINI)
        self.root.geometry(f"{W_MINI}x{H_MINI}+{mini_x}+1")

        bg_fill = TRANSPARENT if self.clear_bg else CARD
        self.capsule(1, 1, W_MINI - 1, H_MINI - 1, 12, fill=bg_fill,
                     outline=LINE if self.clear_bg else "")
        # 上行：时钟 + Codex 5h / 本周 剩余；下行：ZCode 今日剩余 + 页脚信息
        y1, y2 = H_MINI * 0.32, H_MINI * 0.72
        self.clock_id = self.canvas.create_text(
            14, y1, anchor="w", text="00:00:00", fill=CLOCK, font=(FONT, 13, "bold"))
        self.mini_c = self.canvas.create_text(
            118, y1, anchor="e", text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.canvas.create_text(124, y1, anchor="w", text="C·5h",
                                fill=FAINT, font=(FONT, 7, "bold"))
        self.mini_c2 = self.canvas.create_text(
            W_MINI - 14, y1, anchor="e", text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.canvas.create_text(W_MINI - 76, y1, anchor="e", text="C·周",
                                fill=FAINT, font=(FONT, 7, "bold"))
        self.mini_z = self.canvas.create_text(
            118, y2, anchor="e", text="--", fill=SUB, font=(FONT, 11, "bold"))
        self.canvas.create_text(124, y2, anchor="w", text="Z·今日",
                                fill=FAINT, font=(FONT, 7, "bold"))
        self.mini_foot = self.canvas.create_text(
            W_MINI - 14, y2, anchor="e", text="", fill=FAINT, font=(FONT, 8))

        self.menu.delete(0, "end")
        if not hasattr(self, "pin_var"):
            self.pin_var = tk.BooleanVar(value=self.pinned)
        else:
            self.pin_var.set(self.pinned)
        self.menu.add_checkbutton(label="固定位置（固定后不可拖动）",
                                  variable=self.pin_var, command=self.on_pin_menu)
        self.menu.add_command(label="背景：切换为透明" if not self.clear_bg else "背景：切换为实心",
                              command=self.toggle_bg)
        self.menu.add_command(label="展开", command=self.build_card)
        self.menu.add_command(label="立即刷新", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)

    # ---------- 悬停展开按钮组（图钉/最小化/关闭） ----------

    def _btn_meta(self, key):
        return {
            "pin": dict(sym="◆" if self.pinned else "◇",
                        txt="解除固定" if self.pinned else "固定位置", w=64,
                        sym_fill=ACCENT if self.pinned else FAINT, hover=ACCENT),
            "min": dict(sym="—", txt="最小化", w=60,
                        sym_fill=FAINT, hover=ACCENT),
            "close": dict(sym="✕", txt="关闭", w=48,
                          sym_fill=FAINT, hover=BAD),
        }[key]

    def on_btn_enter(self, key):
        self._cancel_btn_jobs()
        for k, b in self.btns.items():
            if k != key:
                for item in (b["bg"], b["sym"], b["txt"]):
                    self.canvas.itemconfig(item, state="hidden")
        self._animate_btn(key, self._btn_meta(key)["w"])

    def on_btn_leave(self, key):
        self._cancel_btn_jobs()
        self._btn_job = self.root.after(150, lambda: self._animate_btn(key, 16))

    def _cancel_btn_jobs(self):
        job = getattr(self, "_btn_job", None)
        if job:
            self.root.after_cancel(job)
            self._btn_job = None

    def _animate_btn(self, key, target):
        self._btn_job = None
        b = self.btns[key]
        meta = self._btn_meta(key)
        if b["w"] < target:
            b["w"] = min(target, b["w"] + 5)
        else:
            b["w"] = max(target, b["w"] - 5)
        x = b["x"]
        self.canvas.coords(b["bg"], *capsule_pts(
            x + 8 - b["w"], Y_TITLE - 8, x + 8, Y_TITLE + 8, 8))
        expanded = target > 16 and b["w"] >= target - 8
        self.canvas.itemconfig(b["txt"], state="normal" if expanded else "hidden")
        self.canvas.itemconfig(b["bg"], outline=meta["hover"] if expanded else FAINT)
        self.canvas.itemconfig(b["sym"], fill=meta["hover"] if expanded else meta["sym_fill"])
        if target <= 16 and b["w"] <= 16:
            for k, b2 in self.btns.items():  # 收回完成，恢复相邻按钮
                if k != key:
                    self.canvas.itemconfig(b2["bg"], state="normal")
                    self.canvas.itemconfig(b2["sym"], state="normal")
        if b["w"] != target:
            self._btn_job = self.root.after(16, lambda: self._animate_btn(key, target))

    # ---------- 通用 ----------

    def toggle_pin(self):
        self.set_pin(not self.pinned)

    def toggle_bg(self):
        save_config(bg="clear" if not self.clear_bg else "solid")
        (self.build_mini if self.mode == "mini" else self.build_card)()

    def on_pin_menu(self):
        """checkbutton 点击后 var 已翻转，从这里单向同步到状态。"""
        self.set_pin(self.pin_var.get())

    def set_pin(self, pinned):
        self.pinned = pinned
        save_config(pinned=pinned)
        if hasattr(self, "pin_var"):
            self.pin_var.set(pinned)
        if self.mode == "card" and hasattr(self, "btns"):
            self.canvas.itemconfig(self.btns["pin"]["sym"],
                                   text="◆" if pinned else "◇",
                                   fill=ACCENT if pinned else FAINT)

    def capsule(self, x1, y1, x2, y2, r, **kw):
        return self.canvas.create_polygon(capsule_pts(x1, y1, x2, y2, r), smooth=True, **kw)

    def keep_on_top(self):
        """无框 topmost 小窗会被抢前台的应用压住，定时续权置顶。"""
        self.root.attributes("-topmost", True)
        self.root.after(5000, self.keep_on_top)

    def tick(self):
        """时钟每秒对齐墙钟刷新，避免 after(1000) 的累积漂移。"""
        now = time.time()
        self.canvas.itemconfig(self.clock_id, text=time.strftime("%H:%M:%S"))
        self.root.after(int((1 - now % 1) * 1000) + 20, self.tick)

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def on_press(self, event):
        self._dx, self._dy = event.x, event.y
        self._press_root = (self.root.winfo_x(), self.root.winfo_y())

    def on_drag(self, event):
        if self.pinned:
            return
        x = self.root.winfo_x() + event.x - self._dx
        y = self.root.winfo_y() + event.y - self._dy
        self.root.geometry(f"+{x}+{y}")

    def on_release(self, event):
        moved = abs(self.root.winfo_x() - self._press_root[0]) + \
            abs(self.root.winfo_y() - self._press_root[1])
        if self.mode == "mini" and moved < 4:
            self.build_card()  # 迷你条单击 = 展开
            return
        if moved >= 4:
            if self.mode == "mini":
                save_config(mini_x=self.root.winfo_x())
            else:
                save_config(x=self.root.winfo_x(), y=self.root.winfo_y())

    def draw_fill(self, attr, y, pct, color):
        old = getattr(self, attr, None)
        if old:
            self.canvas.delete(old)
        span = W - 2 * PAD
        width = max(BAR_H, span * pct / 100)
        fill = self.capsule(PAD, y, PAD + width, y + BAR_H, BAR_H / 2, fill=color, outline="")
        setattr(self, attr, fill)

    def refresh(self):
        # 官方实时查询放后台线程（冷启约 2-4 秒，不能卡 UI），完成后覆盖显示
        self._live_seq = getattr(self, "_live_seq", 0) + 1
        seq = self._live_seq
        threading.Thread(target=self._live_worker, args=(seq,), daemon=True).start()

        try:
            data = load_usage()
        except OSError as e:
            data = None
            if self.mode == "card":
                self.canvas.itemconfig(self.foot_id, text=f"读取失败: {e}")

        if self.mode == "mini":
            self._refresh_mini(data)
            self.root.after(REFRESH_MS, self.refresh)
            return

        if data is None:
            self.root.after(REFRESH_MS, self.refresh)
            return
        rl, usage, ctx_win, ts = data
        self._render_card(rl, usage, ctx_win, ts, live=False)
        self.root.after(REFRESH_MS, self.refresh)

    def _live_worker(self, seq):
        live = load_live_rate_limits()
        if live is None or seq != getattr(self, "_live_seq", 0):
            return  # 查询失败或已被新一轮刷新取代
        self._live_data = live
        try:
            usage = load_usage()
        except OSError:
            usage = None
        if self.mode == "mini":
            self._refresh_mini(usage)
        elif usage:
            self._render_card(usage[0], usage[1], usage[2], usage[3], live=True)

    def _render_card(self, rl, usage, ctx_win, ts, live):
        if live:
            rl = self._live_data  # 实时值优先，覆盖本地快照
        primary = rl["primary"]
        used = primary.get("used_percent") or 0.0
        remain = 100.0 - used
        self.canvas.itemconfig(self.b1_value, text=f"剩 {remain:.0f}%", fill=level_color(remain))
        self.draw_fill("b1_fill", Y_BAR1, remain, level_color(remain))
        resets_at = primary.get("resets_at")
        self.canvas.itemconfig(self.b1_sub, text=fmt_countdown(resets_at) if resets_at else "")

        secondary = rl.get("secondary")
        if isinstance(secondary, dict):
            wremain = 100.0 - (secondary.get("used_percent") or 0.0)
            self.canvas.itemconfig(self.b2_value, text=f"剩 {wremain:.0f}%", fill=level_color(wremain))
            self.draw_fill("b2_fill", Y_BAR2, wremain, level_color(wremain))
            wreset = secondary.get("resets_at")
            wsub = f"{int((wreset - time.time()) // 86400)} 天后重置" if wreset else ""
            self.canvas.itemconfig(self.b2_sub, text=wsub)
        else:
            self.canvas.itemconfig(self.b2_value, text="--", fill=SUB)
            self.canvas.itemconfig(self.b2_sub, text="")

        z = load_zcode_usage()
        if z:
            zremain = z["remaining"] / z["total"] * 100
            self.canvas.itemconfig(self.z_value, text=f"剩 {zremain:.0f}%",
                                   fill=level_color(zremain))
            self.draw_fill("z_fill", Y_ZBAR, zremain, level_color(zremain))
            zsub = f"{z['remaining'] / 1e6:.1f}M"
            if z.get("period_end"):
                zsub += f" · {fmt_countdown(z['period_end'])}"
            self.canvas.itemconfig(self.z_sub, text=zsub)
        else:
            self.canvas.itemconfig(self.z_value, text="--", fill=SUB)
            self.canvas.itemconfig(self.z_sub, text="今日暂无数据")

        foot = ""
        if isinstance(usage, dict) and ctx_win:
            pct = min(100.0, (usage.get("total_tokens") or 0) / ctx_win * 100)
            foot = f"上下文 {pct:.0f}%"
        if live:
            foot = f"{foot} · 实时" if foot else "实时"
        elif ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                age = max(0, (datetime.now().astimezone() - dt).total_seconds())
                rel = "刚刚" if age < 60 else \
                    f"{int(age // 60)} 分钟前" if age < 3600 else f"{int(age // 3600)} 小时前"
                foot = f"{foot} · 数据{rel}" if foot else f"数据{rel}"
            except ValueError:
                pass
        self.canvas.itemconfig(self.foot_id, text=foot)

        self.root.after(REFRESH_MS, self.refresh)

    def _refresh_mini(self, data):
        """迷你条：上行 Codex 5h/周剩余，下行 ZCode 今日剩余 + 余额。"""
        try:
            z = load_zcode_usage()
        except OSError:
            z = None
        if getattr(self, "_live_data", None):
            self._apply_mini(self._live_data, live=True)
        elif data:
            self._apply_mini(data[0], live=False)
        if z:
            zremain = z["remaining"] / z["total"] * 100
            self.canvas.itemconfig(self.mini_z, text=f"{zremain:.0f}%",
                                   fill=level_color(zremain))
            if hasattr(self, "mini_foot"):
                self.canvas.itemconfig(
                    self.mini_foot, text=f"{z['remaining'] / 1e6:.1f}M 剩")

    def _apply_mini(self, rl, live):
        primary = rl["primary"]
        remain = 100.0 - (primary.get("used_percent") or 0.0)
        self.canvas.itemconfig(self.mini_c, text=f"{remain:.0f}%",
                               fill=level_color(remain))
        secondary = rl.get("secondary")
        if isinstance(secondary, dict):
            wremain = 100.0 - (secondary.get("used_percent") or 0.0)
            self.canvas.itemconfig(self.mini_c2, text=f"{wremain:.0f}%",
                                   fill=level_color(wremain))
        if hasattr(self, "mini_foot"):
            cur = self.canvas.itemcget(self.mini_foot, "text")
            base = cur.replace(" · 实时", "").replace("实时", "").strip()
            self.canvas.itemconfig(
                self.mini_foot, text=f"{base} · 实时" if live else base)


if __name__ == "__main__":
    UsageWidget()
