# A 股个股深度分析标准流程 · 规格说明

## Intent

把已经跑了约 30 只个股、迭代到 v4.6 的分析方法论，从「一份 2100 行的个人文档」变成
「一个能被触发、能被执行、能被维护的 skill」。

核心判断：**这套方法论的资产不是它的章节结构，而是它踩过的坑。** 每一个数字、每一条口径规则，
背后都有一只具体的票把原来的读法推翻过（特变电工的非经常性反转、阳光电源的 TTM 高基数、
中微公司的分母污染、中国船舶的假净现金）。因此本 skill 的第一原则是**逐字保真**：
references 里的内容是从原文机械切分出来的，不重写、不概括、不"优化表述"——概括会丢掉
"差 2.24 倍"这种唯一能让人记住为什么必须扣合同负债的细节。

第二个判断：**流程的价值在于闸门，不在于步骤。** 十一个阶段谁都能列，难的是"哪一步不过就该停"。
所以 SKILL.md 的主体是七道硬闸门的判据与失败处置，而不是阶段说明。

## Scope

In scope：
- 非 ST 的沪深主板 / 创业板 / 科创板单只个股的深度分析
- P0–P7 全链路：数据闸门 → 池交叉 → 三级缠论 → 基本面口径 → 事件面 → 主力行为 →
  赔率 → 进场 → 退出 → Jev 自洽 → 横向对比
- 报告骨架、每日批量摘要口径、规则实验室与回测验证路径

Out of scope：
- ST / \*ST（±5% 涨跌幅、退市博弈、保壳修饰，七条模板假设同时失效）
- 指数、板块、宏观、ETF 组合层分析
- 全市场筛选与策略开发（走 `stockdb-strategy-dev`）
- 裸取数、接口开发（走 `a-stock-data`）
- 缠论理论教学（走 `czsc-thinking`）
- 任何形式的买卖建议。本 skill 输出结构位置、赔率、失效条件，不输出指令

## Users And Trigger Context

- Primary users：做 A 股个股研究、需要"这票能不能碰、什么价位、错了怎么退"的人
- Common user requests：
  - "分析一下 600150"
  - "这只票怎么样，能不能买"
  - "给我一份 XX 的深度报告"
  - "赔率多少 / 止损放哪 / 分批怎么分"
  - "缠论结构上看现在处于什么位置"
  - "对比一下这几只票"

- **Should trigger**（8 条，用于验收触发精度）：
  1. 分析中国船舶
  2. 600150 这只票能进吗
  3. 帮我做一份宁德时代的深度报告
  4. 这票赔率怎么样、止损应该放哪里
  5. 从基本面和技术面完整看一下 XX
  6. 这几只票横向对比一下谁更强
  7. 它的扣非和归母差这么多，是什么原因
  8. 现在这个位置适合中线拿 6 个月吗

- **Should not trigger**（6 条，用于验收误触发）：
  1. 今天大盘怎么样（指数，非个股）
  2. 帮我筛一下全市场连续涨停的票（→ `stockdb-strategy-dev`）
  3. 帮我写个脚本抓全部A股日K（→ `a-stock-data` / `stockdb-strategy-dev`）
  4. 什么是缠论的中枢（→ `czsc-thinking`）
  5. 北向资金今天流入多少（单点数据查询，不需要全流程）
  6. 帮我回测一个组合策略（组合层，非单票）

- 边界情形：用户只说"看一下 XX"且上下文是持仓管理 → 仍应触发（属个股分析）；若上下文是选股池构建 → 不触发。

## Evidence Model

- **数据来源必须可追溯**：行情走 stockdb（本地，主）+ easy-tdx（辅），财报/筹码/资金/研报走 westock MCP，
  行业与估值分位走 easy-tdx。每个数字须能回答"哪个源、哪一天"。
- **`dataAsOf` 是报告的一等公民**：所有数字挂在同一个交易日下；不同日期的数字不得混在一个判断里。
  2026-11-10 实测 stockdb 停在 20261109、easy-tdx 已到 20261110 —— 证明"两源默认同步"是错误假设。
- **口径优先于数值**：比值类指标必须两个口径互校取更差；分母被污染的 PE 分位一律作废；
  并表年份不构造时间序列分位。
- **自我推翻必须留痕**：报告固定含「自我推翻记录」一节，写清最初结论、推翻它的数字、替换后的说法。
- **缺口显式化**：`references/known-gaps.md` 的 P0 级缺口在报告里必须标注，不得当作已解决。
- **Jev 只作交叉验证**：置信 < 0.3 的格作废；分数与结论同向但置信低即"伪一致"，同样不得引用。
  结论不得依赖 Jev 单独成立。

## Structure Contract

```text
ashare-stock-analysis/
├── 个股分析流程.md                   ★ 方法论权威正文（v4.6，2120 行）；桌面副本是它的导出物
├── SKILL.md                        入口：铁律 / 适用范围 / 执行顺序 / 七道闸门 / 路由表 / 自检
├── SPEC.md                         本文件：设计意图、触发边界、证据模型、维护约定
├── SOURCES.md                      provenance：内容从哪来、正向/反向生成
├── CONTRIBUTING.md                 迭代手册：一次升版的标准动作、版本号规则、冲突处理
├── references/
│   ├── nav-overview.md             文档结构 / 阶段总览（导航；保证备份完整）
│   ├── pipeline-p0-p2.md           P0 数据闸门 / P1 池交叉 / P2 三级缠论
│   ├── pipeline-p3-fundamentals.md P3 五条口径规则 + 三道前置闸门
│   ├── pipeline-p4-p5.md           P3.5 事件面 / P4 主力 / P5 赔率 / P5.5 进场 / P5.6 退出
│   ├── pipeline-p6-p7.md           P6 Jev / P7 横向对比
│   ├── data-interfaces.md          数据分工 / 巡检 / 字段坑 / 工具清单
│   ├── engineering-defects.md      13 类工程缺陷 + 前复权 + 缓存与熔断
│   ├── output-template.md          报告骨架 / 每日摘要口径
│   ├── rule-lab-backtest.md        规则实验室 / 闸门增量测试 / 退出与组合回测
│   ├── case-calibration.md         v1→v4.6 版本演进 + 十票校准汇总
│   └── known-gaps.md               已知不足（P0/P1/P2 三级）
└── scripts/
    ├── preflight.py                开工前接口巡检（三探 + 环境自检 + dataAsOf 判定）
    ├── check_tables.py             Markdown 表格列数校验（断表检测）
    ├── rebuild_references.py       文档 → references 切分（SPEC 是行号的唯一定义处）
    ├── merge_references.py         references → 文档 反向重建（备份可还原性验证）
    └── release.py                  迭代收尾流水线：版本 → 切分 → 断表 → 回填验证 → 提交
```

约定：
- **权威正文是仓库根的 `个股分析流程.md`**；桌面副本与 `references/` 都是它的派生物，
  两者的改动都不回流。改方法论只改权威正文。
- `SKILL.md` 里出现的每个 `references/*.md` 与 `scripts/*.py` 都必须可直接找到；新增文件必须同步路由表。
- references 只做"按查询需要聚焦"，不做主题大杂烩；文件名要能预测内容。
- **数值改动只能来自权威正文改完后重跑 `rebuild_references.py`**，不允许在 references 里手改数字。
- **切分边界只在 `rebuild_references.py` 的 `SPEC` 里定义一次**；`merge_references.py` 与 `release.py`
  都从它导入，避免三份行号各自漂移。

## Validation

1. `scripts/rebuild_references.py` 幂等：连续两次运行 md5 一致（已验证）。
2. `scripts/check_tables.py references/*.md` → 60 张表 0 异常；源文档 60 张表 0 异常。
3. **备份可还原（最关键）**：`scripts/merge_references.py --verify <原文档>` → 内容级一致，2112 有效行。
   这是"skill 作为方法论备份"这条定位的唯一硬证据；没有它，references 只是碎片而非备份。
4. `scripts/release.py` 五步全过（版本一致 / 切分成功 / 无断表 / 回填一致 / 仓库状态可读）。
5. `quick_validate.py` 结构校验通过（frontmatter、必填字段、被引用的文件存在）。
6. `scripts/preflight.py` 在本机实测通过，并正确报出两源日期不一致。
7. 触发精度：以上 8 条 should-trigger / 6 条 should-not-trigger 人工核对。
8. 覆盖校验：源文档 2120 行**全部**落入 references（含导航两段），无遗漏、无重复。

## Maintenance

- **权威正文升版**（v4.6 → v4.7）：改仓库根的 `个股分析流程.md` → 改标题版本号 →
  `release.py --commit --push --export <桌面路径>`。它会串起版本校验、SPEC 重切、断表校验、
  备份回填验证与导出；SPEC 行号若因章节增删而移动，需先手工更新那双重定位锚点。
- **新增闸门**：先写进权威正文对应阶段，再在 SKILL.md §3 表里加一行，两处必须同步
  （references 由正文生成，所以只改正文即可，但 SKILL.md 的手写摘要要跟上）。
- **新增参考文件**：必须有明确的"何时打开"，并在 §4 路由表登记，否则不新增。
- **数值纪律**：references 中的数字只能由脚本从权威正文带入；人工编辑只允许改标题层级与导读行。
- **桌面副本**：只由 `--export` 生成。手改桌面那份等于改了一份会被下次导出覆盖的临时文件。

## Open Gaps

1. **宿主路径耦合**：`data-interfaces.md` 与 `preflight.py` 含本机绝对路径（托管 venv、工作区目录）。
   这不是疏忽——这套流程依赖本地 stockdb 与本地脚本，脱离本机无法运行。代价是本 skill 不可移植，
   换机需改路径。已在 `data-interfaces.md` 开头标注。
2. **仅单票**：横向对比（P7）只能处理手工给定的 2–10 只，不支持全市场排序。
3. **P0 级缺口继承**：`known-gaps.md` 里 PE/PB 时间序列分位缺失、并表年份分位不可构造等问题未解决，
   skill 只是把它们显式化，没有消除。
4. **未附完整示例报告**：references 里有多处案例数字，但没有一份从头到尾的完整样例报告可供对照。
   （可考虑把 `中国船舶600150_个股分析_20261110.md` 收为 `references/worked-example.md`，待确认。）
