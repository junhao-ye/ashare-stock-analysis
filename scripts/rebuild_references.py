# -*- coding: utf-8 -*-
"""维护工具：把方法论文档按「查询需要」重新切分成 references/*.md。

什么时候用：方法论文档升版（v4.6 → v4.7）后，改下面的 SPEC 切片边界再重跑，
不要手工逐段复制——那样必然漏段、且数值容易被顺手改错。

原则：
1. 逐字迁移，不改任何数值（数值是这份方法论的核心资产）。
2. 切片边界用锚点文本断言，行号漂移会直接报错，不会静默错位。
3. 代码围栏内的 # 行不参与标题处理。

用法：
    python rebuild_references.py                    # 用默认源文档路径
    python rebuild_references.py --src <文档.md>
    python rebuild_references.py --dst <输出目录>    # 默认本 skill 的 references/
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_SRC = Path(r"C:\Users\mai_k\Desktop\个股分析流程.md")
DEFAULT_DST = Path(__file__).resolve().parent.parent / "references"

lines: list[str] = []
TOTAL = 0


def slice_of(start: int, end: int | None, anchor: str) -> list[str]:
    """1-indexed, inclusive。end=None 表示切到文末。anchor 必须是 start 行的前缀（去空白）。"""
    end = TOTAL if end is None else end
    if anchor:
        got = lines[start - 1].strip()
        if not got.startswith(anchor):
            raise SystemExit(f"锚点不匹配 L{start}: 期望以 {anchor!r} 开头，实际 {got!r}")
    return lines[start - 1:end]


def demote(block: list[str], by: int = 0) -> list[str]:
    """把 markdown 标题升降 by 级（by=0 即原样），跳过代码围栏内部。"""
    out, fence = [], False
    for ln in block:
        s = ln.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            out.append(ln)
            continue
        if not fence and s.startswith("#"):
            m = re.match(r"^(#{1,6})(\s+)", ln)
            if m:
                lvl = min(max(len(m.group(1)) + by, 2), 6)
                out.append("#" * lvl + ln[len(m.group(1)):])
                continue
        out.append(ln)
    return out


def trim_blank_edges(block: list[str]) -> list[str]:
    while block and not block[0].strip():
        block = block[1:]
    while block and not block[-1].strip():
        block = block[:-1]
    return block


# 文件名 -> (标题, 何时打开, [(start, end, anchor), ...])
SPEC = {
    "pipeline-p0-p2.md": (
        "P0–P2 · 数据闸门 / 量化池交叉 / 技术结构",
        "每次分析的第一步。判定标的是否可分析（ST 预筛）、数据是否可用（分红对账 / 跳空检测）、"
        "系统池子怎么打分、以及日/周/月三级缠论结构读数。",
        [(59, 107, "## 适用范围"), (278, 414, "### P0 · 数据闸门")],
    ),
    "nav-overview.md": (
        "导航 · 文档结构 / 阶段总览",
        "想知道方法论的章节地图、各阶段耗时与目的，或重建完整文档时。这两段是导航性质，"
        "SKILL.md 有各自的改写版，但原文保留在此，以保证 references 是完整备份。",
        [(108, 169, "## 文档结构"), (257, 277, "## 1. 总览")],
    ),
    "pipeline-p3-fundamentals.md": (
        "P3 · 基本面（五条强制口径规则 + 三道前置闸门）",
        "读到财报数字时。这里是全流程唯一的「数字真实性」防线：归母/扣非并列、OCF 双口径、"
        "分母污染闸门、PE/PB 背离四象限、EV 公式必扣合同负债、营运资本四步验证、一致预期反推。",
        [(415, 787, "### P3 · 基本面")],
    ),
    "pipeline-p4-p5.md": (
        "P3.5–P5.6 · 事件面 / 主力行为 / 赔率 / 进场 / 退出",
        "基本面看完之后。解释业绩异动归因（事件面）、判断资金结构（八问 + 三规则）、"
        "算多口径赔率（含持有期维度与含息附则）、给进场与退出触发条件。",
        [(788, 1112, "### P3.5 · 事件面")],
    ),
    "pipeline-p6-p7.md": (
        "P6–P7 · Jev 语义判断 / 横向对比",
        "报告成稿前。P6 用分数×置信四象限做自相矛盾检查（含「伪一致」陷阱）；"
        "P7 只在同时分析 ≥2 只时启用，按 24 项逐层筛。",
        [(1113, 1270, "### P6 · Jev 语义判断")],
    ),
    "data-interfaces.md": (
        "数据分工 / 接口巡检 / 工具清单",
        "开工前与取数报错时。哪类数据走哪个源、三个探针怎么打、哪些字段有坑、"
        "MCP 工具与本地脚本各自负责什么。",
        [(170, 256, "## 0. 数据分工"), (2050, None, "## 9. 配套文件")],
    ),
    "engineering-defects.md": (
        "数据质量与工程缺陷（13 类）",
        "任何数字看着不对时先查这里。前复权失真、赔率口径重写、超时熔断、缓存清理，"
        "以及十票连跑挖出的 13 类工程缺陷——每一条都曾直接改写过结论。",
        [(1588, 1911, "## 5. 数据质量与工程")],
    ),
    "output-template.md": (
        "输出模板 / 每日必看摘要",
        "写报告时。§6 是单票报告骨架（一句话结论 → P0…P7 → 自我推翻记录）；"
        "§4 是每日批量筛选的摘要口径。",
        [(1486, 1587, "## 4. 每日输出"), (1933, 1963, "## 6. 输出模板")],
    ),
    "rule-lab-backtest.md": (
        "规则库与回测验证",
        "要新增一条规则、或质疑某条规则有没有用时。rule_lab 实验室、闸门增量测试、"
        "退出规则回测、组合层回测四条路径，以及各自的统计裁决口径。",
        [(1271, 1485, "## 3. 规则库与验证"), (2034, 2049, "## 8. 落地情况")],
    ),
    "case-calibration.md": (
        "版本演进 / 十票校准史",
        "要写新规则、或想知道某条规则是被哪只票打出来的时候。v1→v4.6 每一版的触发案例、"
        "改了什么、起因是什么，以及十票连跑汇总的层级判定。",
        [(3, 58, "> v1 归纳自"), (1912, 1932, "### 5.6 十票连跑汇总")],
    ),
    "known-gaps.md": (
        "已知不足（P0 / P1 / P2 三级）",
        "交付前自检，以及任何「这个结论有多可信」的问题。P0 级缺口直接压低结论可信度，"
        "必须在报告里显式标注，不得当作已解决。",
        [(1964, 2033, "## 7. 已知不足")],
    ),
}


def main() -> int:
    global lines, TOTAL
    ap = argparse.ArgumentParser(description="重新切分 references/")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="方法论文档路径")
    ap.add_argument("--dst", default=str(DEFAULT_DST), help="输出目录")
    a = ap.parse_args()

    src, dst = Path(a.src), Path(a.dst)
    if not src.exists():
        raise SystemExit(f"源文档不存在：{src}")
    dst.mkdir(parents=True, exist_ok=True)
    lines = src.read_text(encoding="utf-8").splitlines()
    TOTAL = len(lines)

    report = []
    for fname, (title, when, ranges) in SPEC.items():
        body: list[str] = []
        for start, end, anchor in ranges:
            body.extend(demote(slice_of(start, end, anchor)))
            body.append("")
        body = trim_blank_edges(body)

        header = [
            f"# {title}",
            "",
            f"> **何时打开**：{when}",
            f"> **来源**：`{src.name}` 逐字迁移（原文 {TOTAL} 行）。"
            "数值未经改写，改动只发生在标题层级与「何时打开」导读行。",
            "",
            "---",
            "",
        ]
        text = "\n".join(header + body).rstrip() + "\n"
        # newline="\n" 是必须的：Windows 上默认会把 \n 翻成 \r\n，
        # 而 .gitattributes 要求 LF → 每次重跑都产生一排「diff 为空却显示已修改」的幽灵变更。
        (dst / fname).write_text(text, encoding="utf-8", newline="\n")
        report.append((fname, len(text.splitlines()), len(text)))

    print(f"{'file':38s} {'lines':>6s} {'bytes':>8s}")
    for f, n, b in report:
        print(f"{f:38s} {n:6d} {b:8d}")
    print(f"{'TOTAL':38s} {sum(x[1] for x in report):6d} {sum(x[2] for x in report):8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
