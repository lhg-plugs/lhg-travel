#!/usr/bin/env python3
"""lhg-travel 硬门②：写行程文件时若缺价格声明或含价格承诺，给出即时警告。

触发：PostToolUse / Write|Edit。只检查 .md/.txt 文件：
  - 含机票/酒店/价格字样但无"以官方平台为准"声明 → 警告补声明
  - 含"实时价格/最低价保证/保证有房"承诺 → 警告删除
命中则 additionalContext 提醒，不拦截（写草稿是用户的自由，
分享前有 pre_share_guard 硬门兜底）。

逃生：LHG_TRAVEL_HOOKS_OFF=1。内部出错 fail-open。零第三方依赖。
"""

import json
import os
import re
import sys

PRICE_RE = re.compile(r"机票|酒店|价格|¥")
DISCLAIMER_RE = re.compile(r"以官方平台为准")
PROMISE_RE = re.compile(r"实时价格|当前最低价|最低价保证|保证有房|一定有票|实时房价")

TEXT_EXTS = {".md", ".txt", ".text"}


def main() -> int:
    if os.environ.get("LHG_TRAVEL_HOOKS_OFF") == "1":
        return 0
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail-open

    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return 0
    if not os.path.isfile(path):
        return 0

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return 0  # fail-open

    warns = []
    for i, ln in enumerate(text.split("\n"), 1):
        if DISCLAIMER_RE.search(ln):
            continue
        m = PROMISE_RE.search(ln)
        if m:
            warns.append("第%d行价格承诺「%s」：本插件不承诺实时价格，请删除并补声明" % (i, m.group(0)))
    if PRICE_RE.search(text) and not DISCLAIMER_RE.search(text):
        warns.append("全文出现机票/酒店/价格但无价格声明：请补上"
                     "「机票/酒店实时价格与库存请以官方平台为准自行核实，本插件只做行程框架规划」")

    if not warns:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext":
                "⚠️ 行程文件价格声明检查：\n- " + "\n- ".join(warns) +
                "\n分享前 pre_share_guard 硬门会拦截含 blocker 的分享。",
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
