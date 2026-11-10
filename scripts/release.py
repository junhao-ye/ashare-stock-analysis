#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次迭代的收尾流水线：版本校验 → 重新切分 → 断表校验 → 备份完整性验证 → 提交。

为什么把这几步串起来：它们单独跑都很简单，但**漏跑任何一步都会静默留下一份坏备份**——
漏 rebuild 则 references 落后于文档；漏 verify 则不知道备份还完不完整；
漏版本校验则标题写 v4.6、正文是 v4.7（这个错误已经真实发生过一次）。
串联后任一步失败即中止，不会带着坏状态往下走。

用法：
    python release.py                                  # 只检查，不改仓库
    python release.py --commit -m "feat: 升到 v4.7"      # 检查全过后提交
    python release.py --commit -m "..." --push          # 再推送到 origin
    python release.py --export "C:/Users/me/Desktop/个股分析流程.md"
                                                       # 全过后导出桌面副本
    python release.py --src <文档.md>                    # 指定源文档（默认＝仓库根那份）

退出码：0 全通过 / 1 有步骤失败 / 2 环境问题（文档或目录缺失）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import rebuild_references as rb  # noqa: E402
import merge_references as mr    # noqa: E402

SKILL_MD = ROOT / "SKILL.md"
SOURCES_MD = ROOT / "SOURCES.md"
REF_DIR = ROOT / "references"

OK, BAD, SKIP = "✅", "❌", "⏭"


def step(n: int, total: int, name: str) -> None:
    print(f"\n[{n}/{total}] {name}")
    print("─" * 60)


def check_versions(src: Path) -> bool:
    """方法论版本必须在三处一致：文档标题 / SKILL.md / SOURCES.md。"""
    if not src.exists():
        print(f"{BAD} 源文档不存在：{src}")
        return False

    first = src.read_text(encoding="utf-8").splitlines()[0]
    m = re.search(r"v(\d+\.\d+)", first)
    doc_v = f"v{m.group(1)}" if m else None

    skill_text = SKILL_MD.read_text(encoding="utf-8") if SKILL_MD.exists() else ""
    m2 = re.search(r"方法论正文\s*(v\d+\.\d+)", skill_text)
    skill_v = m2.group(1) if m2 else None

    m3 = re.search(r"个股分析流程\.md[`）)]*\s*[（(]\s*(v\d+\.\d+)", SOURCES_MD.read_text(encoding="utf-8")) \
        if SOURCES_MD.exists() else None
    sources_v = m3.group(1) if m3 else None

    skill_ver = None
    m4 = re.search(r"^version:\s*(\S+)", skill_text, re.M)
    if m4:
        skill_ver = m4.group(1)

    print(f"  文档标题      {doc_v or '未找到'}")
    print(f"  SKILL.md      {skill_v or '未找到'}   （skill 自身版本 {skill_ver or '未找到'}）")
    print(f"  SOURCES.md    {sources_v or '未找到'}")

    found = [v for v in (doc_v, skill_v, sources_v) if v]
    if len(set(found)) == 1 and doc_v:
        print(f"{OK} 方法论版本一致：{doc_v}")
        return True
    if not found:
        print(f"{BAD} 三处都没嗅探到版本号")
    else:
        print(f"{BAD} 版本漂移：{sorted(set(found))} —— 改版本时必须三处同步")
    return False


def run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser(description="迭代收尾流水线")
    ap.add_argument("--src", default=str(rb.DEFAULT_SRC), help="方法论文档路径（默认＝仓库根那份）")
    ap.add_argument("--export", metavar="目标路径", help="全部通过后把权威文档导出到该路径（如桌面副本）")
    ap.add_argument("--commit", action="store_true", help="检查全过后提交")
    ap.add_argument("-m", "--message", help="提交信息（--commit 必填）")
    ap.add_argument("--push", action="store_true", help="提交后推送到 origin")
    a = ap.parse_args()

    src = Path(a.src)
    py = sys.executable
    total = 5
    failures: list[str] = []

    step(1, total, "版本一致性")
    if check_versions(src):
        pass
    else:
        failures.append("版本一致性")

    step(2, total, "重新切分 references")
    ok, out = run([py, str(HERE / "rebuild_references.py"), "--src", str(src)])
    print(out.rstrip() if out.strip() else "(无输出)")
    if not ok:
        failures.append("重新切分")
        print(f"{BAD} 切分失败：锚点不匹配通常意味着文档章节被改名/移动，需同步更新 SPEC 行号")

    step(3, total, "断表校验")
    # 权威正文与根目录文档也要查：断表最早就是从权威正文里长出来的（§9.2 那处）
    targets = sorted(REF_DIR.glob("*.md")) + sorted(p for p in ROOT.glob("*.md") if p != src)
    if src.exists():
        targets.insert(0, src)
    ok, out = run([py, str(HERE / "check_tables.py"), *[str(p) for p in targets]])
    print("\n".join(out.rstrip().splitlines()[-4:]))
    if not ok:
        failures.append("断表校验")
    elif "处异常" in out and "0 处异常" not in out:
        failures.append("断表校验")
        print(f"{BAD} 存在断表")

    step(4, total, "备份完整性（references → 文档回填）")
    ok, out = run([py, str(HERE / "merge_references.py"), "--verify", str(src)])
    print(out.rstrip() if out.strip() else "(无输出)")
    if not ok:
        failures.append("备份完整性")

    step(5, total, "仓库状态")
    ok, out = run(["git", "-C", str(ROOT), "status", "--short"])
    if not ok:
        print(f"{SKIP} 不是 git 仓库，跳过")
    else:
        changes = [ln for ln in out.splitlines() if ln.strip()]
        if changes:
            print(f"  待提交 {len(changes)} 项：")
            for ln in changes[:20]:
                print("   " + ln)
            if len(changes) > 20:
                print(f"   …（还有 {len(changes) - 20} 项）")
        else:
            print("  工作区干净，无待提交变更")

        if a.commit:
            if not a.message:
                print(f"{BAD} --commit 需要 -m 提交信息")
                failures.append("提交")
            elif failures:
                print(f"{BAD} 前序步骤失败，拒绝提交（避免留下坏备份）")
                failures.append("提交")
            elif not changes:
                print(f"{SKIP} 无变更，跳过提交")
            else:
                for cmd in (["add", "-A"], ["commit", "-m", a.message]):
                    ok2, o2 = run(["git", "-C", str(ROOT), *cmd])
                    if not ok2:
                        print(o2)
                        failures.append("提交")
                        break
                else:
                    print(f"{OK} 已提交")
                    if a.push:
                        ok3, o3 = run(["git", "-C", str(ROOT), "push", "origin", "HEAD"])
                        print(f"{OK} 已推送" if ok3 else o3)

    print("\n" + "═" * 60)
    if failures:
        print(f"{BAD} 未通过：{'、'.join(failures)}")
        return 1
    print(f"{OK} 全部通过：版本一致、references 已刷新、无断表、备份可还原")

    if a.export:
        target = Path(a.export)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes().replace(b"\r\n", b"\n")
        target.write_bytes(data)
        print(f"{OK} 已导出到 {target}（{len(data)} 字节 / LF）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
