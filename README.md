<!-- About 简介（推送后填写到仓库 About 栏）：
旅行规划专家：目的地/天数/预算/偏好→日行程→POI清单→预算表→打包清单，附16条确定性审计规则（时间冲突/预算求和/POI完整度/疲劳提醒）。只做行程框架规划，不承诺实时价格。 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-travel
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, travel, itinerary, trip-planning, budget, poi -->

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="lhg-travel — 旅行规划专家">
</p>

> **一句话介绍**：旅行规划专家：目的地/天数/预算/偏好→日行程→POI清单→预算表→打包清单，附16条确定性审计规则（时间冲突/预算求和/POI完整度/疲劳提醒）。只做行程框架规划，不承诺实时价格。

**一键安装**：在 Claude Code 里运行

```bash
/plugin marketplace add lhg-plugs/lhg-travel
/plugin install lhg-travel@lhg-plugs
```

> **⚠️ 价格声明（先看这个）**：机票/酒店实时价格与库存请以官方平台为准自行核实，本插件只做行程框架规划。
> 任何"实时最低价""保证有房"类表述都会被审计脚本判 blocker 并拦截——本插件不承诺任何实时价格。

## 它能帮你做出什么

每条产出先过确定性脚本自查，再交人工复核清单——数字全部数自仓库里的审计脚本，不靠模型"自觉"。

| 自查脚本 | 规则数 | blocker | warning | nit | 覆盖 |
|---|---|---|---|---|---|
| `scripts/audit/travel_audit.py` | 16 | 4 | 10 | 2 | 时间、预算、POI、声明、格式、完整 |
| **合计** | **16** | **4** | **10** | **2** | |

- **零 LLM 成本**：规则是纯 Python 脚本，零第三方依赖，本地运行。
- **坏 / 好对照可验**：`fixtures/` 里备有坏/好用例，冒烟测试断言命中情况。
- **冒烟全绿**：`python3 smoke_test.py` 53 项全部通过（JSON 合法、frontmatter 完整、命令/skill/agent 齐全）。

## 它是什么

`lhg-travel` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **4 个命令**（小白入口）：`travel` 旅行规划一条龙、`travel-budget` 旅行预算表编制、`travel-check` 行程自查、`travel-pack` 打包清单生成
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：lhg-tv-budget, lhg-tv-emergency, lhg-tv-plan, lhg-tv-poi
- **2 个专家 agent**：travel-auditor, travel-planner
- **2 个 hooks**（`hooks/`：post_plan_warn.py, pre_share_guard.py），关键操作前自动把关
- **16 条确定性自查规则**：纯 Python 脚本，见上表

## 为什么是它

不是一个 prompt，而是一套互相兜底的机制：

1. **确定性脚本（机器）+ 人工复核清单（人）**：先跑 `scripts/` 下的审计脚本（共 16 条规则），发现分三级：**blocker**（必须修）、**warning**（修或写豁免理由）、**nit**（顺手修）；再按对应 skill 的复核清单过一遍脚本抓不到的（内容真实性、越权、口径一致）。blocker 清零才算做完；为清零改规则算作弊，不许。
2. **硬门，不是提醒**：hooks 在关键操作前自动拦截或警告（见 `hooks/`），而不是只在文档里写一句"请注意"。
3. **方法论沉淀在 skill 里**：流程、检查清单、口径都写在 `skills/` 的方法论里，命令只是入口；换个 agent 平台也能复用同一套做法。
4. **可验，不是可信**：`fixtures/` 备有坏/好对照用例，`smoke_test.py` 一键验证，规则有没有生效、自己跑一遍就知道。

## 快速上手

```bash
# 1. 安装（Claude Code 里运行）
/plugin marketplace add lhg-plugs/lhg-travel
/plugin install lhg-travel@lhg-plugs

# 2. 旅行规划一条龙：目的地/天数/预算/偏好输入→日行程规划→POI清单→预算表→打
/lhg-travel:travel 北京 --days 3 --budget 9000 --style 美食
```

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-travel:travel` | 旅行规划一条龙：目的地/天数/预算/偏好输入→日行程规划→POI清单→预算表→打包清单，附价格声明与确定性审计。 | `/lhg-travel:travel 北京 --days 3 --budget 9000 --style 美食` |
| `/lhg-travel:travel-budget` | 旅行预算表编制：总预算→交通/住宿/餐饮/门票/应急分项→求和校验→占比诊断，输出可执行的预算表。 | `/lhg-travel:travel-budget 北京 --total 9000` |
| `/lhg-travel:travel-check` | 行程自查：跑16条确定性审计规则（时间冲突/预算求和/POI完整度/价格声明），输出分级报告。 | `/lhg-travel:travel-check 行程.md --fix` |
| `/lhg-travel:travel-pack` | 打包清单生成：目的地+天数+季节→证件/衣物/电子/药品/其他五类清单，附行前检查表。 | `/lhg-travel:travel-pack 北京 --days 3 --season 秋` |

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你需要旅行规划一条龙时 → 用 `/lhg-travel:travel`
- 你需要旅行预算表编制时 → 用 `/lhg-travel:travel-budget`
- 你需要行程自查时 → 用 `/lhg-travel:travel-check`

**什么时候不用：**

- 你只需要其中一个零散能力时 → 本插件是成套流程，单点需求用更轻量的 skill 更合适
- 你希望 AI 完全自由发挥、不接受任何自查与硬门时 → 它的规则审计与 hooks 会介入（可关，但那就别装它）
- 你的场景不在上面命令表覆盖范围内时 → 先看命令表，没有对应命令就别硬套

## 目录结构

```
lhg-travel/
├── smoke_test.py          # 一键冒烟测试
├── ATTRIBUTION.md         # 灵感来源与许可声明
├── LICENSE                # MIT
├── README.md              # 本文件
├── .claude-plugin/
├── agents/
├── assets/
├── commands/
├── fixtures/
├── hooks/
├── scripts/
├── skills/
```

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（本次实测 53 项全部通过）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-travel/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

同门插件见 [lhg-plugs](https://github.com/lhg-plugs)，86 个插件的完整矩阵在 [marketplace](https://github.com/lhg-plugs/marketplace) 维护。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
