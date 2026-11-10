# 数据分工 / 接口巡检 / 工具清单

> **何时打开**：开工前与取数报错时。哪类数据走哪个源、三个探针怎么打、哪些字段有坑、MCP 工具与本地脚本各自负责什么。
> **来源**：`个股分析流程.md` 逐字迁移（原文 2120 行）。数值未经改写，改动只发生在标题层级与「何时打开」导读行。

---

## 0. 数据分工

| 数据                               | 来源                                                | 说明                               |
| -------------------------------- | ------------------------------------------------- | -------------------------------- |
| **行情（日/周/月/历史批量）**               | **stockdb（主）+ `qfq.py` 前复权**                      | 本地库、无频限，**大批量历史首选**              |
| 当日盘中数据                           | easy-tdx `tdx_src.fetch`                          | stockdb 通常滞后一天；仅作补充              |
| 全市场快照（PE/市值/EPS/净资产/主力净流入/换手/量比） | **easy-tdx** `snapshot()`                         | 5447 只，首次 33s → 之后 0s（当日 pkl 缓存） |
| **资金流分层（超大单/大单/中单/小单）**         | **westock MCP** `data_fund_flow`                  | **v4 改为主源**：四项加总 ≈0，可自校验；含 5/10/20 日累计 |
| 资金流单值快查（一个"主力净额"数字）            | easy-tdx `capital_flow()`                         | 快，但**分层字段不自洽**，只能当单值用           |
| 行业归属 / 同业成分                      | **easy-tdx** `industry_of()` / `peers_industry()` | 128 个 HY 行业板块索引（首次 70s，当日缓存）     |
| 估值分位                             | **easy-tdx** `valuation_pct()`                    | 全市场 PE_TTM 截面分位（⚠ 分母塌陷时作废，见 P3）  |
| **三大财务报表**                       | **westock MCP** `data_finance`                    | 唯一来源                             |
| **筹码分布 / 股东名单 / 融资明细**          | **westock MCP** `data_chip` / `data_shareholder` / `data_fund_margin` | 唯一来源        |
| **一致预期 / 研报评级**                   | **westock MCP** `data_consensus` / `data_report`  | 唯一来源（v4 起强制做 Q4 反推校验）            |
| **事件面（政策/一次性损益/并表变化）**          | **westock MCP** `data_news_search` + 研报标题扫描     | v4 新增 P3.5，四只票全靠这一层解释业绩            |

> ⚠️ **easy-tdx 使用边界（2026-11-04 用户明确）**：  
> **行情以 stockdb 为主，easy-tdx 为辅。尤其历史行情大批量取数，easy-tdx 有限制**，  
> 不要把 easy-tdx 当全市场历史批量取数的主通道。它的正确定位是：  
> 全市场快照 / 资金流 / 行业板块 / 估值分位（stockdb 没有）+ 当日盘中数据。
>
> ⚠️ **盘中量比会失真**：easy-tdx 当日是"半天成交量 ÷ 全天均量"（600060 盘中量比 0.69，收盘后 stockdb 算出 2.2）。  
> **收盘后的量比判断必须用 stockdb 的完整K线**，easy-tdx 只用于盘中即时看。

> ⚠️ **两个字段坑**：
>
> 1. `dividend_yield` 不可靠（600060 返回 −0.04%，实际 3.42%）→ **股息率必须自己算**（分红TTM ÷ 市值）
> 2. `pe_ttm` 与财报口径差 8.7%（14.61 vs 13.43）→ **用 PE 时不要与 MCP 的 EPS 混用**

---

## 0.5 开工前接口巡检（v4 新增，每次分析前必做）

**最小集三探**（加起来 3 秒，但能挡掉 80% 的"拿旧数据硬跑"）：

```bash
# ① stockdb 一根K线（注意：只认纯数字代码）
curl -s "http://127.0.0.1:7899/?cmd=vals&t=日k:600089&json=1" | head -c 100
# ② easy-tdx 一根K线 + 行业（顺带验缓存是否当日）
python -c "import sys;sys.path.insert(0,'common');import tdx_src;r=tdx_src.fetch('600089',5);print(r[-1]['date'],tdx_src.industry_of('600089'))"
# ③ Jev 凭据与连通
python -c "import sys;sys.path.insert(0,'common');import jev_stock;print(jev_stock.load_key() is not None)"
```

**2026-11-09 复检（v4 定稿前，两轮结果合并）**

| 环节 | 调用 | 结果 | 耗时 | 判定 |
|---|---|---|---|---|
| stockdb 连通 | `cmd=vals&t=日k:300274` | 200｜**3618 根**｜最新 **20261106**｜收 81.97 | 0.24s | ✅ |
| **stockdb 代码格式** | `cmd=vals&t=日k:sz300274`（带前缀） | **返回 `[]` 空表** | 0.00s | ❌ **已知坑，见下** |
| qfq 适配层 | `qfq.fetch('300274')` | 3618 根前复权｜最新 20261106 | 0.24s | ✅ |
| easy-tdx 日线 | `tdx_src.fetch('300274',300)` | 300 根｜最新 20261106｜收 81.97 | 2.59s | ✅ |
| easy-tdx 行业 | `industry_of('300274')` | `['光伏设备']` | 0.00s | ✅ |
| easy-tdx 快照 | `snapshot()` | **5580 只**（当日 pkl 命中） | 0.00s | ✅ |
| easy-tdx 估值分位 | `valuation_pct('300274')` | PE **12.62** / pct **8.0** / median 37.3 / n 4024 | 0.01s | ✅ ⚠ |
| easy-tdx 资金流 | `capital_flow / flow_summary` | 可返回但**字段不自洽** | 0.29s | ⚠ **已弃用，见 P4** |
| TA-Lib | `talib.get_functions()` | **201 个函数**，v0.8.1 | 1.30s | ✅ |
| czsc | `import czsc` | v1.0.2 | 0.68s | ✅ |
| pandas / numpy | — | 3.0.6 / 2.5.3 | — | ✅ |
| **Jev** | `jev_stock.judge(build_state(facts))` | 返回正常（17/100@0.43、28/100@0.26）| 1.10s | ✅ |
| **westock MCP** | quote / fund_flow / finance / chip / shareholder / report / consensus / margin / news_search | 全部正常返回 | — | ✅ |

> ⚠ **估值分位口径注意**：`valuation_pct` 返回的 PE 12.62 = MCP 的 **`pe_lyr`**（去年报静态），
> 而 MCP `pe_ratio`（TTM）是 **20.78**、`pe_fwd` 是 19.31。
> **三者差 65%，报告里必须写清楚用的是哪个。** 默认用 TTM，分位仅作参考。

> ✅ **MCP 资金流自洽性已验证**（2026-11-06 阳光电源）：
> 超大单 −2.08 亿 + 大单 −2.11 亿 + 中单 −0.80 亿 + 小单 +5.00 亿 = **0.00**
> 且 `MainNetFlow = JumboNetFlow + BlockNetFlow` 严格成立 → **可以作为主力行为的唯一依据**。

**四条巡检纪律**

1. **stockdb 的 `t=` 只认纯数字代码**（`日k:300274` 有效，`日k:sz300274` 静默返回空表）。
   `qfq.fetch('sz300274')` 拿到 0 行就是这么来的——**空表不报错，最容易漏**。带前缀一律先剥掉。
2. **两个源头的最新交易日分别记录**。v4 实测 stockdb 与 easy-tdx **都已到 20261106**（此前 stockdb 曾滞后一天），
   但不能假设永远同步 → 取两者较新者，并标注 `dataAsOf`。
3. **任一环节失败按 §0 边界回退，不硬跑**：easy-tdx 挂了 → 回退 stockdb+qfq（并标注"跳空推断，跨除权处有偏差"）；
   Jev 挂了 → 报告明确写"本版未含语义判断层"；stockdb 与 easy-tdx 都挂 → **停止，不编造**。
4. **Python 必须用托管 venv**（v4 新增）：
   ```
   C:\Users\mai_k\.workbuddy\binaries\python\envs\default\Scripts\python.exe
   ```
   系统默认 python **没有 numpy/pandas/talib**，直接跑 `tdx_src` 会 `ModuleNotFoundError: numpy`。
   `qfq.py` 只依赖标准库，所以能用默认 python 跑——**但不要因此以为环境是好的**。

---


## 9. 配套文件

| 文件                                         | 作用                                     |
| ------------------------------------------ | -------------------------------------- |
| `common/tdx_src.py`                        | easy-tdx 数据层（行情/快照/资金流/行业/同业）          |
| `common/qfq.py`                            | stockdb 前复权兜底层；**`is_st()` / `limit_of(code, name)` 提供 ST 与涨跌停口径** |
| `chan-workbench/chan_diag.py`              | 单票缠论诊断（日/周/月）                          |
| `triangle-workbench/reversal_scan.py`      | 困境反转池（v1/v2 双口径）                       |
| `triangle-workbench/deep_pullback_scan.py` | 深回踩池                                   |
| `triangle-workbench/breakout_scan.py`      | 区间突破（含回测）                              |
| `triangle-workbench/watch_levels.py`       | 观察名单每日监控                               |
| `triangle-workbench/watchlist.json`        | 观察名单配置                                 |
| `chan-workbench/stock_report.py`           | **单票全流程报告生成器（P0~P5 一体输出）**             |
| `common/jev_stock.py`                      | 个股 Jev 语义判断层（P6）                       |
| `common/jev_rules.py`                      | 规则 Jev 语义复审（健全度/右尾/可执行）                |
| **`triangle-workbench/rule_lab.py`**       | **规则实验室：新规则必须过的回测+Jev 闸门**            |
| `triangle-workbench/rule_registry.json`    | 规则注册表（每条规则的统计 + Jev 分 + 裁决）            |
| **`triangle-workbench/exit_backtest.py`**  | **退出规则回测：止损/止盈/时间止损的增量对比**             |
| **`common/cleanup.py`**                    | **累积缓存自动清理（kline pkl / snapshot / digest 快照）** |
| `triangle-workbench/audit_backtest.py`     | 回测口径审计（涨停买不进 / 幸存者偏差 / 流动性）            |

### 9.1 MCP 工具清单（v4 实测可用，2026-11-09 复检）

单票分析实际会调用以下 9 类，**全部通过**：

| 工具 | 用途 | 返回要点 |
|---|---|---|
| `data_quote` | 现价/涨跌/量比/换手 | 量比是判断"缩量上涨"的关键 |
| `data_kline` | 日K（前复权） | 与 stockdb 交叉验证用 |
| `data_finance` | 三大报表（`num=8` 取 8 期） | **必须取 8 期**才能看单季趋势 |
| `data_consensus` | 一致预期 | 目标价 + 2026~2028E EPS/净利/对应PE |
| `data_chip` | 筹码 | 平均成本、获利盘%、集中度90/70 |
| `data_shareholder` | 股东户数 | 户数骤降 = 筹码集中 |
| `data_report` | 研报 | **标题往往直接写出业绩原因**，扫标题比读正文高效 |
| `data_fund_flow` | 资金流四层 | 超大/大/中/小单，加总 ≈0 可自验（**替代 easy-tdx**） |
| `data_fund_margin` | 融资融券 | 融资余额/流通市值 = 拥挤度 |
| `data_north_holding` | 北向持股 | 季度变化，滞后 1.5 个月，仅作弱确认 |
| `data_news_search` | 资讯检索 | **关键词不要太长**，`"特变电工 多晶硅 输变电 订单"` 返回空，`"特变电工"` 返回 4 条 |

> **检索踩坑**：多关键词组合会触发 AND 匹配导致 0 结果。**先用单公司名，再人工筛。**

### 9.2 本地脚本清单（v4 实际使用）

| 脚本 | 调用方式 | 产出去向 |
|---|---|---|
| `chan-workbench/stock_report.py` | `python stock_report.py sz300274 --md <路径>` | `_报告.md`（P0~P5 原始输出） |
| `common/jev_stock.py` | `from jev_stock import build_state, judge, format_lines` | 控制台/报告 P6 段 |
| `common/tdx_src.py` | `fetch / snapshot / industry_of / valuation_pct` | P1、P2 辅助 |
| `common/qfq.py` | `fetch('300274')`（**纯数字**） | stockdb 兜底 |
| `tools/jev_judge.py`（旧工作区） | `python jev_judge.py --selftest` | 凭据自检 |

> **标准四步工作流**（每只票都这样跑）：
> 1. MCP 批量取数（quote / finance×8 / consensus / chip / shareholder / report / fund_flow / margin / news）
> 2. 写入 `common/_cache/fund_<code>.json`（供 `stock_report.py` 消费）
> 3. 跑 `stock_report.py` 生成原始报告
> 4. **手工复核并修正脚本缺陷**（§5.5 五类），再组装最终报告

**其余脚本与文件的去向**（v4.6 补表头：原表在此处被上段引用块插断，8 行成了无表头的孤立表格，渲染必断）

| 脚本 / 文件 | 说明 |
|---|---|
| `common/div_sync.py`                       | 分红方案同步 + 前复权精度对拍（`--cover/--audit/--merge`） |
| `common/qfq_rebuild.py`                    | 反推因子实验脚本（**已证伪，仅留档**）                   |
| `docs/退出规则回测.md`                       | 退出规则完整结果表（3 信号 × 11 种退出）                  |
| **`triangle-workbench/portfolio_backtest.py`** | **组合层回测：净值曲线 / 回撤 / Sharpe / 空仓期**      |
| `triangle-workbench/portfolio_report.html`  | 净值曲线图（策略 vs 全市场等权）                        |
| **`common/daily_digest.py`**               | **每日必看摘要器：两工作台收口成 A/B/C 三档（降噪核心）**      |
| `common/_state/digest_<date>.json`         | 每日快照（用于 diff：新增/持续 N 日/掉出）              |
| `common/_cache/fund_<code>.json`           | MCP 数据缓存（财报/预期/研报/融资/筹码），由 agent 取数后写入 |

*文档版本 v4.6 · 2026-11-10 · 十票连跑校准（含 EV 公式修正） · 研究口径，不构成投资建议。*
