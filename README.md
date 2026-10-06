# ⚡ codex-usage-widget

A tiny always-on-top desktop widget for **Windows** that shows your
[OpenAI Codex](https://openai.com/codex/) and [ZCode](https://bigmodel.cn) plan
usage in real time — pure local file reading, no network calls, no API keys.

**English** | [中文说明见下方](#中文说明)

![screenshot](https://img.shields.io/badge/platform-Windows%2010%2F11-blue) ![license](https://img.shields.io/badge/license-MIT-green)

## What it looks like

A rounded dark card floating on your desktop (or fully transparent mode):

```
⚡ usage monitor                  ◇  —  ✕
           03:15:01              ← live clock, ticking every second

CODEX
5-hour window              剩 21%  ← colored by how much is left
██████████░░░░░░░░░░░░░░░░░░░░
10 h 29 min until reset

Weekly quota               剩 83%
████░░░░░░░░░░░░░░░░░░░░░░░░░░
6 days until reset

ZCODE
Daily quota                剩 79%
███████████████░░░░░░░░░░░░░░░
78.8M · 20 h 52 min until reset
─────────────────────────────────
context 74% · data 1 min ago
```

Colors by remaining quota: **green ≥40% · amber 20–40% · red <20%**.

## Features

- **Live clock** with second hand (wall-clock aligned, no drift)
- **Codex**: 5-hour window + weekly quota (remaining %, reset countdown)
- **ZCode**: daily token pool (remaining % + absolute value + reset countdown)
- **Mini bar mode**: click `—` to collapse into a slim top bar
  (`clock · Codex% · ZCode%`), click it again to expand
- **Pin button**: lock the widget position against accidental drags
- **Transparent background**: toggle between dark card and fully clear
- **Hover-to-reveal buttons**: small symbols expand into labeled capsules
- **Position memory**: both modes remember where you put them
- Single file, **no third-party dependencies** — just Python + tkinter

## How it works

Both tools write usage snapshots to local files. The widget just reads the
latest one every 30 seconds:

| Source | File | Field |
|---|---|---|
| Codex | `~/.codex/sessions/**/*.jsonl` | `rate_limits` (official snapshot, same data as `/usage`) |
| ZCode | `~/.zcode/v2/logs/YYYY-MM-DD.log` | `payload.data.balances[0]` (daily token pool) |

Nothing is sent anywhere. If Codex/ZCode isn't running, the widget shows the
last snapshot and its age.

## Install

Requires **Windows 10/11** and **Python 3.8+** ([python.org](https://www.python.org/downloads/) — tick "Add to PATH").

```bat
git clone https://github.com/yh13860671231/codex-usage-widget.git
cd codex-usage-widget
START.bat
```

Or just double-click `codex_usage_widget.pyw`.

**Start with Windows**: press `Win+R`, type `shell:startup`, put a shortcut to
`START.bat` in there.

## Usage

| Action | How |
|---|---|
| Move | drag anywhere |
| Pin position | click `◇` (turns solid blue `◆` = locked) |
| Minimize to top bar | click `—`, click the bar to restore |
| Transparent / solid | right-click → 背景 toggle |
| Close | hover `✕` → click, or right-click → 退出 |
| Refresh | automatic every 30 s, or right-click → 立即刷新 |

## Known limitations

- Codex stops writing snapshots when your quota is exhausted, so the widget
  can freeze at the last value (e.g. "3% left" when it's actually 0) until the
  window resets or you run Codex again.
- The fully transparent mode needs a dark wallpaper for readability.
- Windows only (uses `overrideredirect` + `-transparentcolor` + Win32 DWM).

## 中文说明

一个 Windows 桌面置顶悬浮窗，实时显示 OpenAI Codex 和智谱 ZCode
的套餐用量。纯本地读文件，不联网、不需要 API Key，单文件零依赖。

- **显示**：秒级时钟；Codex 5 小时窗口 / 本周额度剩余；ZCode 当日 token 池剩余；按剩余量绿/黄/红变色
- **交互**：拖动移动（位置记忆）、图钉锁位置、`—` 一键收缩成顶部迷你条、背景透明/实心切换、右键菜单
- **原理**：读 `~/.codex/sessions/**` 和 `~/.zcode/v2/logs/` 里工具自动写入的限额快照
- **安装**：装好 Python 后双击 `codex_usage_widget.pyw` 或 `START.bat`；开机自启把快捷方式放进 `shell:startup`
- **已知限制**：额度耗尽后 Codex 停止回写快照，显示会冻结在最后一个值；透明模式在浅色壁纸上可读性差

## License

[MIT](LICENSE)
