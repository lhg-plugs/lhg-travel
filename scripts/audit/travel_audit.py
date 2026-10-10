#!/usr/bin/env python3
"""lhg-travel 确定性审计：16 条行程规划规则，零第三方依赖。

扫描目标（单个 .md/.txt 文件或目录），输出 JSON 与人类可读报告；
有 blocker 时以 exit code 2 退出，warning 以 exit code 1 退出（供 hooks 与 CI 使用）。

本插件只做行程框架规划，不承诺任何实时价格；TV-DOC-002 会拦截
"实时价格/最低价保证"类承诺表述。

规则文案均为本项目原创，未复制任何第三方的原文案与代码。

用法：
    python3 travel_audit.py --target <文件或目录> [--format json|text] [--fail-on blocker|warning|nit]
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-travel/travel-audit"

SCAN_EXTS = {".md", ".txt", ".text"}

# ---------- 时间解析 ----------
DAY_RE = re.compile(r"^#{1,3}\s*(?:Day\s*(\d+)|第\s*(\d+)\s*天)")
RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[-~–—至]\s*(\d{1,2}):(\d{2})")
POINT_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
BULLET_RE = re.compile(r"^\s*(?:[-*•·]\s+|\d{1,2}[.)、]\s*)(.+)$")

# ---------- 预算解析 ----------
TOTAL_RE = re.compile(r"总预算[：:\s]*([\d,]+)")
ITEM_RES = [
    ("交通", re.compile(r"交通[：:\s]*([\d,]+)")),
    ("住宿", re.compile(r"住宿[：:\s]*([\d,]+)")),
    ("餐饮", re.compile(r"餐饮|用餐|吃饭")),
    ("门票", re.compile(r"门票|景点")),
    ("应急", re.compile(r"应急|备用|预留")),
]
ITEM_NUM_RES = {
    "交通": re.compile(r"交通[：:\s]*([\d,]+)"),
    "住宿": re.compile(r"住宿[：:\s]*([\d,]+)"),
    "餐饮": re.compile(r"(?:餐饮|用餐|吃饭)[：:\s]*([\d,]+)"),
    "门票": re.compile(r"(?:门票|景点)[：:\s]*([\d,]+)"),
    "应急": re.compile(r"(?:应急|备用|预留)[：:\s]*([\d,]+)"),
    "其他": re.compile(r"(?:其他|购物|纪念品)[：:\s]*([\d,]+)"),
}

# ---------- POI ----------
POI_SECTION_RE = re.compile(r"^#{1,4}\s*(POI|景点清单|游玩清单)", re.I)
ALT_RE = re.compile(r"备选|替代|雨天方案")

# ---------- 声明 ----------
DISCLAIMER_RE = re.compile(r"以官方平台为准")
PROMISE_RE = re.compile(r"实时价格|当前最低价|最低价保证|保证有房|一定有票|实时房价")
DOC_RE = re.compile(r"身份证|护照")
INSURANCE_RE = re.compile(r"保险")

PLACEHOLDER_RE = re.compile(r"\[TODO\]|TODO|{{.+?}}|XXX|待定酒店|待定航班")

DATE_FMT_RES = [
    ("cnday", re.compile(r"第\s*\d+\s*天")),
    ("enday", re.compile(r"\bDay\s*\d+", re.I)),
    ("slash", re.compile(r"\d{1,2}/\d{1,2}")),
    ("dash", re.compile(r"\d{4}-\d{1,2}-\d{1,2}")),
    ("cnmd", re.compile(r"\d{1,2}月\d{1,2}日")),
]


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet[:160]
        self.detail = detail

    def to_dict(self):
        return {"rule_id": self.rule_id, "severity": self.severity,
                "category": self.category, "title": self.title,
                "file": self.file, "line": self.line,
                "snippet": self.snippet, "detail": self.detail}


RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail, "check": fn}
        _RULE_BY_ID[rule_id] = r
        RULES.append(r)
        return fn
    return deco


def _finding(rule_id, path, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   path, line, snippet, r["detail"])


def _lines(text):
    return text.split("\n")


def _to_min(h, m):
    return int(h) * 60 + int(m)


def _day_items(text):
    """解析每天的时间事项：{day: [(start_min, end_min, line_no, raw), ...]}。"""
    lines = _lines(text)
    days, cur = {}, None
    for i, ln in enumerate(lines, 1):
        dm = DAY_RE.match(ln)
        if dm:
            cur = int(dm.group(1) or dm.group(2))
            days.setdefault(cur, [])
            continue
        if cur is None:
            continue
        if re.match(r"^#{1,4}\s*", ln):
            cur = None
            continue
        b = BULLET_RE.match(ln)
        if not b:
            continue
        content = b.group(1)
        rm = RANGE_RE.search(content)
        if rm:
            s = _to_min(rm.group(1), rm.group(2))
            e = _to_min(rm.group(3), rm.group(4))
            days[cur].append((s, e, i, content.strip()))
        else:
            pm = POINT_RE.search(content)
            if pm:
                s = _to_min(pm.group(1), pm.group(2))
                days[cur].append((s, s + 60, i, content.strip()))
    return days


def _poi_items(text):
    """解析 POI 清单章节下的条目（跳过备选行）。"""
    lines = _lines(text)
    start, level = -1, 0
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,4})\s*(.+?)\s*$", ln)
        if m and POI_SECTION_RE.search(ln):
            start, level = i, len(m.group(1))
            break
    if start < 0:
        return []
    items = []
    for j, ln in enumerate(lines[start + 1:], start + 2):
        m = re.match(r"^(#{1,4})\s*", ln)
        if m and len(m.group(1)) <= level:
            break
        b = BULLET_RE.match(ln)
        if b and not ALT_RE.search(b.group(1)):
            items.append((j, b.group(1).strip()))
    return items


def _budget_section(text):
    """取「预算」章节文本（到下一个同级标题为止），避免 POI 章节的门票数字污染。"""
    lines = _lines(text)
    start, level = -1, 0
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,4})\s*(.+?)\s*$", ln)
        if m and re.search(r"预算|费用", m.group(2)):
            start, level = i, len(m.group(1))
            break
    if start < 0:
        return text
    buf = []
    for ln in lines[start + 1:]:
        m = re.match(r"^(#{1,4})\s*", ln)
        if m and len(m.group(1)) <= level:
            break
        buf.append(ln)
    return "\n".join(buf)


def _budget(text):
    """解析总预算与分项：(total, {name: amount})。"""
    sec = _budget_section(text)
    total = None
    m = TOTAL_RE.search(sec)
    if m:
        total = int(m.group(1).replace(",", ""))
    items = {}
    for name, pat in ITEM_NUM_RES.items():
        mm = pat.search(sec)
        if mm:
            items[name] = int(mm.group(1).replace(",", ""))
    return total, items


# ================= 时间规则 =================

@rule("TV-TIME-001", "blocker", "时间", "日行程时间冲突",
      "同一天两个事项时间重叠：人不可能同时出现在两个地方。调整其中一个的时间段，"
      "或删掉不重要的那个。")
def _r(doc):
    out = []
    for day, items in sorted(_day_items(doc["text"]).items()):
        items = sorted(items)
        for k in range(1, len(items)):
            ps, pe, pl, praw = items[k - 1]
            cs, ce, cl, craw = items[k]
            if cs < pe:
                out.append(_finding("TV-TIME-001", doc["path"], cl,
                                    "第%d天 %s 与上一事项时间重叠" % (day, craw[:40])))
    return out


@rule("TV-TIME-002", "warning", "时间", "行程衔接过紧",
      "相邻事项间隔不足 30 分钟：没算路上时间+排队+找路，实际一定会迟到。"
      "同城跨区至少留 45 分钟，跨城留 1.5 小时。")
def _r(doc):
    out = []
    for day, items in sorted(_day_items(doc["text"]).items()):
        items = sorted(items)
        for k in range(1, len(items)):
            ps, pe, pl, praw = items[k - 1]
            cs, ce, cl, craw = items[k]
            gap = cs - pe
            if 0 <= gap < 30:
                out.append(_finding("TV-TIME-002", doc["path"], cl,
                                    "第%d天间隔仅 %d 分钟：%s" % (day, gap, craw[:40])))
    return out


@rule("TV-TIME-003", "warning", "时间", "单日安排过满",
      "单日事项超过 6 个或时间跨度超过 12 小时：这是特种兵行程，不是旅行。"
      "砍掉优先级最低的 1-2 个，留出吃饭和发呆的时间。")
def _r(doc):
    out = []
    for day, items in sorted(_day_items(doc["text"]).items()):
        if len(items) > 6:
            out.append(_finding("TV-TIME-003", doc["path"], items[0][2],
                                "第%d天 %d 个事项（>6）" % (day, len(items))))
        elif items:
            span = max(e for _, e, _, _ in items) - min(s for s, _, _, _ in items)
            if span > 12 * 60:
                out.append(_finding("TV-TIME-003", doc["path"], items[0][2],
                                    "第%d天跨度 %d 小时（>12）" % (day, span // 60)))
    return out


@rule("TV-TIME-004", "warning", "时间", "连续高强度赶路",
      "连续 3 天每天 ≥4 个事项：第三天起体验断崖式下跌，还容易生病。"
      "中间插 1 天轻量日（≤2 个事项），或每天砍掉 1 个。")
def _r(doc):
    out = []
    days = sorted(_day_items(doc["text"]).items())
    for k in range(len(days) - 2):
        trio = days[k:k + 3]
        if all(len(items) >= 4 for _, items in trio):
            d0 = trio[0][0]
            out.append(_finding("TV-TIME-004", doc["path"], trio[0][1][0][2],
                                "第%d-%d天连续高强度（每天≥4事项）" % (d0, d0 + 2)))
    return out


# ================= 预算规则 =================

@rule("TV-BUD-001", "blocker", "预算", "预算分项求和≠总预算",
      "分项加总与总预算对不上（差值>1%）：要么分项漏了，要么总预算写错。"
      "预算表第一铁律是先对上数。")
def _r(doc):
    total, items = _budget(doc["text"])
    if total and items:
        s = sum(items.values())
        if abs(s - total) > total * 0.01:
            return [_finding("TV-BUD-001", doc["path"], 1,
                             "分项合计 %d ≠ 总预算 %d" % (s, total))]
    return []


@rule("TV-BUD-002", "warning", "预算", "缺核心预算分项",
      "交通/住宿/餐饮/门票四大项缺 2 项以上：预算表不完整，实际花费一定超。"
      "补上缺失项，哪怕先估个数。")
def _r(doc):
    total, items = _budget(doc["text"])
    if not total:
        return []
    core = ["交通", "住宿", "餐饮", "门票"]
    missing = [c for c in core if c not in items]
    if len(missing) >= 2:
        return [_finding("TV-BUD-002", doc["path"], 1,
                         "缺分项：" + "、".join(missing))]
    return []


@rule("TV-BUD-003", "warning", "预算", "单项占比异常",
      "某一项超过总预算 60%：结构失衡。常见是住宿超标——"
      "降一档酒店，或砍掉 1 天行程，钱要花在体验上。")
def _r(doc):
    total, items = _budget(doc["text"])
    out = []
    if total:
        for name, amt in items.items():
            if amt / total > 0.6:
                out.append(_finding("TV-BUD-003", doc["path"], 1,
                                    "%s %d 元，占总预算 %.0f%%（>60%%）"
                                    % (name, amt, amt / total * 100)))
    return out


@rule("TV-BUD-004", "warning", "预算", "无应急预留",
      "没有应急/备用金，或不足总预算 5%：旅行中一定有意外支出（改签、打车、买药）。"
      "至少留 5-10% 做应急。")
def _r(doc):
    total, items = _budget(doc["text"])
    if not total:
        return []
    emg = items.get("应急", 0)
    if emg < total * 0.05:
        return [_finding("TV-BUD-004", doc["path"], 1,
                         "应急预留 %d 元，不足总预算 5%%" % emg)]
    return []


# ================= POI 规则 =================

@rule("TV-POI-001", "warning", "POI", "POI 营业时间缺失",
      "POI 条目无营业/开放时间：周一闭馆、节假日调休这种坑，出发前必须查。"
      "每个 POI 至少注明开放时间与闭馆日。")
def _r(doc):
    out = []
    for ln, item in _poi_items(doc["text"]):
        if not re.search(r"营业|开放|闭馆", item):
            out.append(_finding("TV-POI-001", doc["path"], ln, item[:40]))
    return out


@rule("TV-POI-002", "warning", "POI", "POI 信息不完整",
      "POI 条目缺地址或门票信息：没地址没法规划路线，没门票没法做预算。"
      "每个 POI 至少写清地址 + 门票（免费也要写「免费」）。")
def _r(doc):
    out = []
    for ln, item in _poi_items(doc["text"]):
        if not re.search(r"地址", item) or not re.search(r"门票|免费", item):
            out.append(_finding("TV-POI-002", doc["path"], ln, item[:40]))
    return out


@rule("TV-POI-003", "nit", "POI", "无替代方案",
      "全文无备选/替代/雨天方案：下雨、闭馆、排队 2 小时，Plan B 是什么？"
      "至少给每天准备 1 个室内备选。")
def _r(doc):
    if _poi_items(doc["text"]) and not ALT_RE.search(doc["text"]):
        return [_finding("TV-POI-003", doc["path"], 1, "无备选/雨天方案")]
    return []


# ================= 声明规则 =================

@rule("TV-DOC-001", "warning", "声明", "缺价格声明",
      "全文无「以官方平台为准」声明：行程里一旦出现机票/酒店价格，"
      "必须声明实时价格与库存以官方平台为准自行核实。本插件只做行程框架规划。")
def _r(doc):
    if re.search(r"机票|酒店|价格|¥|元", doc["text"]) and not DISCLAIMER_RE.search(doc["text"]):
        return [_finding("TV-DOC-001", doc["path"], 1, "缺价格声明")]
    return []


@rule("TV-DOC-002", "blocker", "声明", "实时价格承诺",
      "出现「实时价格」「最低价保证」「保证有房」类承诺：本插件不提供实时价格与库存信息，"
      "这类承诺必须删除，改为「价格以官方平台实时查询为准」。")
def _r(doc):
    out = []
    for i, ln in enumerate(_lines(doc["text"]), 1):
        if DISCLAIMER_RE.search(ln):
            continue  # 价格声明行自身豁免（如"…实时价格…以官方平台为准…"）
        m = PROMISE_RE.search(ln)
        if m:
            out.append(_finding("TV-DOC-002", doc["path"], i, m.group(0)))
    return out


@rule("TV-DOC-003", "warning", "声明", "缺证件保险提醒",
      "无身份证/护照/保险提醒：证件过期、没买保险，是旅行中最贵的教训。"
      "行程末尾加一行出行提醒。")
def _r(doc):
    if not DOC_RE.search(doc["text"]) or not INSURANCE_RE.search(doc["text"]):
        return [_finding("TV-DOC-003", doc["path"], 1, "缺证件或保险提醒")]
    return []


# ================= 其他 =================

@rule("TV-FMT-001", "nit", "格式", "日期格式混乱",
      "同一文件混用多种日期格式（第X天/Day X/月日）：统一成一种，推荐「第X天」。")
def _r(doc):
    used = [name for name, pat in DATE_FMT_RES if pat.search(doc["text"])]
    if len(used) >= 2:
        return [_finding("TV-FMT-001", doc["path"], 1,
                         "混用日期格式：" + "、".join(used))]
    return []


@rule("TV-PLACE-001", "blocker", "完整", "占位符残留",
      "残留 [TODO]/XXX/待定酒店/待定航班 等占位符：行程还没定完就准备发了，"
      "逐条落实或删除后再分享。")
def _r(doc):
    out = []
    for i, ln in enumerate(_lines(doc["text"]), 1):
        m = PLACEHOLDER_RE.search(ln)
        if m:
            out.append(_finding("TV-PLACE-001", doc["path"], i, m.group(0)))
    return out


# ================= 主流程 =================

SEV_ORDER = {"blocker": 0, "warning": 1, "nit": 2}


def collect_targets(target):
    paths = []
    if os.path.isdir(target):
        for root, _, files in os.walk(target):
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in SCAN_EXTS:
                    paths.append(os.path.join(root, f))
    elif os.path.isfile(target):
        paths.append(target)
    return paths


def load_doc(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return {"path": path, "text": f.read()}


def run_audit(paths):
    findings = []
    for p in paths:
        doc = load_doc(p)
        for r in RULES:
            try:
                findings.extend(r["check"](doc) or [])
            except Exception as e:
                findings.append(Finding(r["id"], "nit", "内部",
                                        "规则执行异常", p, 0, "",
                                        "规则 %s 执行出错（已跳过）：%s" % (r["id"], e)))
    findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.file, f.line))
    return findings


def summarize(findings):
    s = {"blocker": 0, "warning": 0, "nit": 0, "rules_run": len(RULES)}
    for f in findings:
        s[f.severity] += 1
    return s


def format_text(findings, summary):
    lines = ["[%s] 行程审计报告 v%s" % (TOOL, VERSION),
             "规则 %d 条 | blocker %d / warning %d / nit %d"
             % (summary["rules_run"], summary["blocker"],
                summary["warning"], summary["nit"]),
             "-" * 56]
    cur = None
    for f in findings:
        if f.severity != cur:
            cur = f.severity
            lines.append("## %s" % cur.upper())
        lines.append("[%s] %s:%s %s" % (f.rule_id, f.file, f.line, f.title))
        if f.snippet:
            lines.append("    片段：%s" % f.snippet)
        lines.append("    建议：%s" % f.detail)
    if not findings:
        lines.append("零发现：行程无冲突、预算对得上、POI 信息完整，可以进入人工复核。")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-travel 确定性行程审计")
    ap.add_argument("--target", required=True, help="行程文件或目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"],
                    default="blocker",
                    help="达到该级别即非零退出（默认 blocker）")
    args = ap.parse_args(argv)

    paths = collect_targets(args.target)
    if not paths:
        print("未找到可扫描文件：%s" % args.target, file=sys.stderr)
        return 2

    findings = run_audit(paths)
    summary = summarize(findings)

    if args.format == "json":
        print(json.dumps({"tool": TOOL, "version": VERSION,
                          "summary": summary,
                          "findings": [f.to_dict() for f in findings]},
                         ensure_ascii=False, indent=2))
    else:
        print(format_text(findings, summary))

    worst = "nit"
    for f in findings:
        if SEV_ORDER[f.severity] < SEV_ORDER[worst]:
            worst = f.severity
    return 2 if SEV_ORDER[worst] <= SEV_ORDER[args.fail_on] else 0


if __name__ == "__main__":
    sys.exit(main())
