#!/usr/bin/env python3
"""lhg-travel 硬门①：分享行程前强制审计。

触发：PreToolUse / Bash。命令含"分享/导出/发布/发送"且含
travel/行程/攻略/游记 字样时，视为"准备对外分享行程"，自动跑
travel_audit.py；有 blocker 则拦截。

逃生方式（按推荐度排序）：
  1. 先修掉 blocker 再分享（推荐）。
  2. 紧急情况：LHG_TRAVEL_HOOKS_OFF=1 <原命令>（单次豁免本次 hook）。
  3. /plugin disable lhg-travel（整个插件停用，hooks 不再触发）。

设计原则：脚本内部出错 fail-open 直接放行，不因插件自身故障骚扰用户。
零第三方依赖。
"""

import json
import os
import re
import subprocess
import sys

SHARE_RE = re.compile(r"分享|导出|发布|发送|share|export|publish", re.I)
TRAVEL_RE = re.compile(r"travel|行程|攻略|游记|itinerary", re.I)


def main() -> int:
    if os.environ.get("LHG_TRAVEL_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail-open

    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command", "") or ""
    if not command.strip():
        return 0

    # 非分享类命令：快速放行
    if not (SHARE_RE.search(command) and TRAVEL_RE.search(command)):
        return 0

    # 定位插件目录与审计脚本
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        here = os.path.abspath(__file__)
        plugin_root = os.path.dirname(os.path.dirname(here))
    audit = os.path.join(plugin_root, "scripts", "audit", "travel_audit.py")
    if not os.path.isfile(audit):
        return 0  # fail-open：脚本丢了不拦

    # 审计目标：优先用 --target 参数，否则用当前项目目录
    target = os.environ.get("CLAUDE_PROJECT_DIR", "") or "."
    m = re.search(r"--target\s+(\S+)", command)
    if m:
        target = m.group(1)

    try:
        r = subprocess.run(
            [sys.executable, audit, "--target", target, "--format", "json"],
            capture_output=True, text=True, timeout=60)
        data = json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return 0  # fail-open：审计跑不起来不拦

    summary = data.get("summary", {}) or {}
    blockers = [f for f in data.get("findings", [])
                if f.get("severity") == "blocker"]
    if summary.get("blocker", 0) > 0:
        detail = "\n".join(
            "- [%s] %s:%s %s" % (f.get("rule_id"), f.get("file"),
                                 f.get("line"), f.get("title"))
            for f in blockers[:10])
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    "行程审计发现 %d 个 blocker，分享前必须清零：\n%s\n"
                    "修完重跑 scripts/audit/travel_audit.py 验证；"
                    "紧急豁免：LHG_TRAVEL_HOOKS_OFF=1" % (len(blockers), detail),
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    # 有 warning 时给提醒但不拦截
    if summary.get("warning", 0) > 0:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason":
                    "行程审计发现 %d 个 warning（无 blocker）：建议修完再分享，"
                    "确认分享请继续。" % summary["warning"],
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
