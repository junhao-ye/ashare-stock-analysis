#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""反向重建：把 references/ 还原成一份完整的《个股分析流程》文档。

为什么需要它：这份 skill 被定位为方法论文档的**备份**。若只做单向切分（文档 → references），
一旦原始文档丢失（此前已发生过两次，其中 v4.4 从未进过任何备份、不可恢复），
references 就只是「碎片」，不是备份。本脚本证明并实现反向可还原。

依据：scripts/rebuild_references.py 里的 SPEC 记录了每段的**原始起始行号**。
反向时按该行号排序拼接，即可还原原文档的章节顺序——不依赖文件名顺序，
所以日后新增/调整切片也不会打乱重建结果。

用法：
    python merge_references.py                      # 输出到 stdout
    python merge_references.py -o 个股分析流程.md      # 写文件
    python merge_references.py --verify 原文档.md      # 重建并与原文档比对
    python merge_references.py --verify 原文档.md -o /tmp/rebuilt.md

比对口径：内容级一致（忽略空行数量与行尾空白的差异）。
章节边界处空行数量可能差 1~2 个，这是切分时统一边界格式造成的，不影响内容完整性。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rebuild_references as rb  # noqa: E402  SPEC 的唯一定义处，避免两份行号各自漂移

REF_DIR = HERE.parent / "references"
SKILL_MD = HERE.parent / "SKILL.md"
SOURCES_MD = HERE.parent / "SOURCES.md"

HEADER_SEP = "---"


def strip_header(text: str) -> list[str]:
    """去掉 rebuild 加的文件头（H1 + 何时打开 + 来源 + ---），返回正文行。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == HEADER_SEP:
            return lines[i + 1:]
    return lines


def split_segments(body: list[str], anchors: list[str]) -> list[list[str]]:
    """按锚点把文件正文切回各段。锚点必须按出现顺序单调递增。"""
    idx: list[int] = []
    cursor = 0
    for a in anchors:
        found = None
        for i in range(cursor, len(body)):
            if body[i].strip().startswith(a):
                found = i
                break
        if found is None:
            raise SystemExit(f"锚点未找到：{a!r}（文件内容可能被手改过，或 rebuild 后未重新生成）")
        idx.append(found)
        cursor = found + 1
    segs = []
    for k, start in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(body)
        segs.append(body[start:end])
    return segs


def detect_version() -> str:
    """从 SKILL.md / SOURCES.md 里嗅探方法论版本号，用于重建标题行。"""
    for f, pat in (
        (SKILL_MD, r"方法论正文\s*(v\d+\.\d+)"),
        (SOURCES_MD, r"个股分析流程\.md[`）)]*\s*[（(]\s*(v\d+\.\d+)\s*[）)]"),
        (SOURCES_MD, r"\|\s*版本日期\s*\|\s*([^|]+)\|"),
    ):
        if not f.exists():
            continue
        m = re.search(pat, f.read_text(encoding="utf-8"))
        if m:
            v = m.group(1).strip()
            return v if v.startswith("v") else f"v{v}"
    return "v?"


def merge(title: str | None = None) -> str:
    version = detect_version()
    pieces: list[tuple[int, list[str]]] = []

    for fname, (_t, _w, ranges) in rb.SPEC.items():
        path = REF_DIR / fname
        if not path.exists():
            raise SystemExit(f"缺少参考文件：{path}（先跑 rebuild_references.py）")
        body = strip_header(path.read_text(encoding="utf-8"))
        anchors = [a for (_s, _e, a) in ranges]
        segs = split_segments(body, anchors)
        for (start, _end, _a), seg in zip(ranges, segs):
            while seg and not seg[0].strip():
                seg = seg[1:]
            while seg and not seg[-1].strip():
                seg = seg[:-1]
            pieces.append((start, seg))

    pieces.sort(key=lambda x: x[0])

    # 校验：按原始行号排序后不应有重叠（重叠说明 SPEC 切片互相覆盖，回填会重复内容）
    for i in range(1, len(pieces)):
        prev_start, prev = pieces[i - 1]
        cur_start, _ = pieces[i]
        if prev_start == cur_start:
            raise SystemExit(f"两段起点相同（{cur_start}），SPEC 有重叠，请修正后重跑")

    out: list[str] = ["# 个股分析标准流程 " + version, ""]
    for _start, seg in pieces:
        out.extend(seg)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def normalize(text: str) -> list[str]:
    """比对口径：去行尾空白，把连续空行压成一个，去首尾空行。"""
    rows, blank = [], False
    for ln in text.splitlines():
        s = ln.rstrip()
        if not s:
            if blank:
                continue
            blank = True
            rows.append("")
        else:
            blank = False
            rows.append(s)
    while rows and rows[0] == "":
        rows.pop(0)
    while rows and rows[-1] == "":
        rows.pop()
    return rows


def verify(original: Path, rebuilt_text: str) -> int:
    if not original.exists():
        print(f"✗ 原文档不存在：{original}")
        return 2
    a = normalize(original.read_text(encoding="utf-8"))
    b = normalize(rebuilt_text)

    if a == b:
        print(f"✅ 重建与原文档内容一致（{len(b)} 个有效行）")
        print("   备份可还原：references 未丢失任何章节。")
        return 0

    import difflib

    diff = list(difflib.unified_diff(a, b, fromfile="原文档", tofile="重建", lineterm="", n=1))
    print(f"❌ 内容不一致：原文档 {len(a)} 行 / 重建 {len(b)} 行，差异 {len(diff)} 行")
    for ln in diff[:40]:
        print("   " + ln)
    if len(diff) > 40:
        print(f"   …（还有 {len(diff) - 40} 行）")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="从 references/ 反向重建完整方法论文档")
    ap.add_argument("--verify", metavar="原文档", help="与指定原文档比对")
    ap.add_argument("-o", "--out", help="写入文件（默认 stdout）")
    ap.add_argument("--title", help="覆盖重建标题行（默认自动嗅探版本号）")
    a = ap.parse_args()

    text = merge(a.title)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"已写入 {a.out}（{len(text.splitlines())} 行 / {len(text)} 字符 / {len(text.encode('utf-8'))} 字节）")
    elif not a.verify:
        sys.stdout.write(text)

    if a.verify:
        return verify(Path(a.verify), text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
