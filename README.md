<!-- About 简介（推送后填写到仓库 About 栏）：
旅行规划专家：日行程→POI清单→预算表→打包清单，16条规则审计 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-travel
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, travel, itinerary, trip-planning -->

# lhg-travel：旅行规划专家

> **一句话介绍**：给 AI 助手装上"旅行规划组合拳"——输入目的地/天数/预算/偏好，日行程规划→POI 清单→预算表→打包清单一条龙，16 条确定性规则自动检查时间冲突、预算求和、POI 完整度。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-travel
> /plugin install lhg-travel@lhg-plugs
> ```

> **⚠️ 价格声明（先看这个）**：机票/酒店实时价格与库存请以官方平台为准自行核实，本插件只做行程框架规划。
> 任何"实时最低价""保证有房"类表述都会被审计脚本判 blocker 并拦截——本插件不承诺任何实时价格。

## 它是什么

`lhg-travel` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **4 个命令**（小白入口）：`travel` 规划一条龙，`travel-check` 行程自查，`travel-budget` 预算表，`travel-pack` 打包清单
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等）：行程规划、预算编制、POI 筛选、应急清单
- **2 个专家 agent**：行程规划专家、行程审计专家
- **2 个硬门 hooks**：分享前审计拦截（blocker 未清零不许分享）、写行程文件价格声明检查（均可一键豁免）
- **16 条确定性审计规则**：4 条时间（冲突/衔接/过满/疲劳）+ 4 条预算（求和/分项/占比/应急）+ 3 条 POI + 3 条声明 + 2 条其他，纯 Python、零第三方依赖，秒级出结果

## 4 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-travel:travel` | 目的地/天数/预算/偏好→日行程→POI→预算表→打包清单 | `/lhg-travel:travel 北京 --days 3 --budget 9000 --style 美食` |
| `/lhg-travel:travel-check` | 行程自查：16 条规则审计 + 人工复核 4 项 | `/lhg-travel:travel-check 行程.md --fix` |
| `/lhg-travel:travel-budget` | 预算表：六分项编制→求和校验→占比诊断 | `/lhg-travel:travel-budget 北京 --total 9000` |
| `/lhg-travel:travel-pack` | 打包清单：五类清单 + 行前检查表 | `/lhg-travel:travel-pack 北京 --days 3 --season 秋` |

## 自查说明

自查 = 确定性脚本（机器）+ 人工复核清单（人）：

1. 先跑 `scripts/audit/travel_audit.py --target <行程文件或目录>`，零成本；
2. 发现分三级：**blocker**（时间冲突、预算分项求和≠总预算、实时价格承诺、占位符残留，必须清零）、**warning**（衔接过紧、单日过满、连续赶路、POI 信息不全、缺价格声明、缺证件保险提醒，逐条修）、**nit**（无备选方案、日期格式混乱）；
3. 再按 `travel-check` 命令过一遍脚本抓不到的 4 项（动线顺不顺、节奏合理吗、预算靠谱吗、声明到位吗）。

blocker 清零才算"可分享"；**为清零直接删掉冲突事项而不告诉用户 → 不许**。

## 目录结构

```
lhg-travel/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 4 个命令：travel / travel-check / travel-budget / travel-pack
├── skills/                  # 4 个平台中立 skill（lhg-tv-plan/budget/poi/emergency）
├── agents/                  # 2 个专家 agent（travel-planner / travel-auditor）
├── hooks/                   # 2 个硬门（分享拦截 / 价格声明检查）+ 豁免说明
├── scripts/audit/           # 16 条确定性审计规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（bad/a.md + bad/b.md / good/plan.md）
├── smoke_test.py            # 一键冒烟测试（53 项）
├── ATTRIBUTION.md           # 灵感来源声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用

**什么时候用：**

- 你要去某地玩几天，只有模糊想法 → `/lhg-travel:travel` 一次生成日行程+POI+预算+打包清单
- 行程排好了，吃不准时间现不现实、预算对不对 → `/lhg-travel:travel-check` 先审再出发
- 只想算钱：总预算定了，不知道怎么分 → `/lhg-travel:travel-budget` 六分项一次算清
- 出发前一天，不知道带什么 → `/lhg-travel:travel-pack` 五类清单+行前检查表

**什么时候不用：**

- 你想查"明天北京飞三亚最低多少钱""这家酒店今晚有没有房" → **本插件不干这个**，实时价格与库存请以官方平台为准自行核实
- 你要的是签证办理/代订机票酒店 → 本插件只做行程框架规划，不做预订执行
- 你希望 AI 帮你把"实时最低价保证"写进行程 → **不许**，这是红线，写了就拦截
- 你只想找个旅行攻略抄一抄 → 去抄攻略更快；本插件是"规划+审计"全链路，规划只是起点

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-travel](https://github.com/lhg-plugs/lhg-travel) | 旅行规划专家：日行程→POI→预算表→打包清单，16条规则审计 | `/plugin install lhg-travel@lhg-plugs` |
| *（后续插件在此追加，保持表格格式一致）* | | |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、16 条规则、fixtures 命中、hooks 行为、价格声明）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-travel/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 视频号：搜「刘洪光实名上网」
- 微信：lhgsmsw
