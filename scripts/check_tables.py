#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Markdown 表格列数一致性校验。

为什么需要它：报告里的表格一旦某行多一个 `|`（典型场景是在单元格里写
`|归母−扣非|/|归母|` 这种绝对值符号），渲染时会被切成多列，整张表错位，
而肉眼扫几百行是看不出来的。本次方法论演进中，这个方法实际拦下过两次断表。

用法：
    python check_tables.py 报告.md
    python check_tables.py *.md            # 支持多文件
    python check_tables.py 报告.md --strict # 有异常时退出码 1

判定：
    - 表格块 = 连续的非空、以 `|` 开头的行
    - 首行为表头，第二行为分隔行（必须全部由 -/: 组成）
    - 表头 / 分隔行 / 每行数据的列数必须相等
    - 代码围栏（``` / ~~~）内部的 `|` 行不校验
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEP_CELL = re.compile(r"^:?-{1,}:?$")


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c for c in s.split("|")]


def is_separator(line: str) -> bool:
    cells = [c.strip() for c in split_row(line)]
    return bool(cells) and all(SEP_CELL.match(c) for c in cells if c != "") and any(cells)


def check_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    problems: list[dict] = []
    fence = False
    i = 0
    while i < len(lines):
        s = lines[i].lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            i += 1
            continue
        if fence or not s.startswith("|"):
            i += 1
            continue

        start = i
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1

        if len(block) < 2:
            problems.append({"line": start + 1, "kind": "孤行表格", "detail": "只有一行，无法构成表格"})
            continue

        head_n = len(split_row(block[0]))
        if not is_separator(block[1]):
            problems.append({
                "line": start + 2, "kind": "缺分隔行",
                "detail": f"第 2 行不是 |---| 分隔行：{block[1].strip()[:60]}",
            })
        sep_n = len(split_row(block[1]))
        if sep_n != head_n:
            problems.append({
                "line": start + 2, "kind": "列数不符",
                "detail": f"表头 {head_n} 列 vs 分隔行 {sep_n} 列",
            })
        for j, ln in enumerate(block[2:], start=3):
            n = len(split_row(ln))
            if n != head_n:
                problems.append({
                    "line": start + j, "kind": "列数不符",
                    "detail": f"表头 {head_n} 列 vs 本行 {n} 列 → {ln.strip()[:70]}",
                })
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown 表格列数一致性校验")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--strict", action="store_true", help="有异常时退出码 1")
    a = ap.parse_args()

    total_tables = 0
    total_problems = 0
    for f in a.files:
        p = Path(f)
        if not p.exists():
            print(f"✗ 文件不存在：{p}")
            total_problems += 1
            continue
        probs = check_file(p)
        n_tbl = sum(
            1
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.lstrip().startswith("|") and is_separator(ln)
        )
        total_tables += n_tbl
        total_problems += len(probs)
        status = "✅" if not probs else f"❌ {len(probs)} 处"
        print(f"{status}  {p.name}  ({n_tbl} 张表)")
        for pr in probs:
            print(f"    L{pr['line']:<6} [{pr['kind']}] {pr['detail']}")

    print(f"\n合计：{total_tables} 张表，{total_problems} 处异常")
    return 1 if (a.strict and total_problems) else 0


if __name__ == "__main__":
    sys.exit(main())
