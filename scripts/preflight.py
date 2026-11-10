#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开工前接口巡检（§0.5 的最小集三探 + 环境自检）。

用法：
    python preflight.py --code 600150
    python preflight.py --code 600150 --root "D:\\some\\workspace"

退出码：
    0  关键环节全部可用
    1  stockdb 不可用（但 easy-tdx 可用 → 可降级跑）
    2  两个行情源都不可用 → 停手，不要编造

设计纪律（对应 references/data-interfaces.md 的四条巡检纪律）：
    - stockdb 的 t= 只认纯数字代码，带 sz/sh 前缀会静默返回空表 → 这里先剥前缀再请求，
      并把"剥了前缀"这件事打印出来，避免误以为原样代码可用。
    - 两个源头的最新交易日分别记录，不能假设永远同步 → 分别打印，取较新者作 dataAsOf。
    - 任何一项失败只报错，不抛栈，不让巡检本身变成故障点。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

STOCKDB = "http://127.0.0.1:7899"


def strip_prefix(code: str) -> tuple[str, str | None]:
    """返回 (纯数字代码, 被剥掉的前缀)。stockdb 只认纯数字。"""
    m = re.match(r"^(sh|sz|bj)(\d{6})$", code.strip(), re.I)
    if m:
        return m.group(2), m.group(1).lower()
    return code.strip(), None


def probe_stockdb(code: str, timeout: float = 5.0) -> dict:
    out: dict = {"ok": False, "rows": 0, "last": None, "close": None, "ms": None}
    url = f"{STOCKDB}/?cmd=vals&t={urllib.parse.quote('日k:' + code)}&json=1"
    t0 = dt.datetime.now()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        out["ms"] = round((dt.datetime.now() - t0).total_seconds(), 2)
        data = json.loads(raw)
        # 实测返回是「字典列表」；兼容 {"data": [...]} 与 {代码: [...]} 两种包装
        rows = data
        if isinstance(data, dict):
            rows = data.get("data") or data.get("vals")
            if rows is None:
                rows = next((v for v in data.values() if isinstance(v, list)), [])
        if isinstance(rows, dict):
            rows = next((v for v in rows.values() if isinstance(v, list)), [])
        if not isinstance(rows, list) or not rows:
            out["err"] = "返回空表（常见原因：代码带了前缀 / 该股停牌无K / 代码不存在）"
            return out
        out["rows"] = len(rows)
        last = rows[-1]
        if isinstance(last, dict):
            out["last"] = str(last.get("date"))
            out["close"] = last.get("close")
            out["name"] = last.get("name")
        else:
            out["last"] = str(last[0])
            out["close"] = last[2] if len(last) > 2 else None
        out["ok"] = True
    except Exception as e:  # noqa: BLE001 - 巡检不应抛栈
        out["err"] = f"{type(e).__name__}: {e}"
    return out


def probe_tdx(code: str, root: Path) -> dict:
    out: dict = {"ok": False, "last": None, "close": None, "industry": None}
    common = root / "common"
    if not (common / "tdx_src.py").exists():
        out["err"] = f"未找到 {common / 'tdx_src.py'}（用 --root 指定工作区根目录）"
        return out
    sys.path.insert(0, str(common))
    try:
        import tdx_src  # type: ignore

        rows = tdx_src.fetch(code, 5)
        if not rows:
            out["err"] = "fetch 返回空"
            return out
        out["last"] = str(rows[-1].get("date"))
        out["close"] = rows[-1].get("close")
        out["industry"] = tdx_src.industry_of(code)
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["err"] = f"{type(e).__name__}: {e}"
    return out


def probe_jev(root: Path) -> dict:
    out: dict = {"ok": False, "has_key": False}
    common = root / "common"
    if (common / "jev_stock.py").exists():
        sys.path.insert(0, str(common))
    try:
        import jev_stock  # type: ignore

        key = jev_stock.load_key()
        out["has_key"] = key is not None and key is not False
        out["key_tail"] = str(key)[-4:] if isinstance(key, str) and len(key) > 8 else None
        out["ok"] = out["has_key"]
        if not out["has_key"]:
            out["err"] = "凭据缺失：检查 TYPESAFE_API_KEY / JEV_API_KEY 或工作区 .env"
    except Exception as e:  # noqa: BLE001
        out["err"] = f"{type(e).__name__}: {e}"
    return out


def probe_env() -> dict:
    out: dict = {}
    try:
        import numpy, pandas  # noqa: F401

        out["numpy"] = numpy.__version__
        out["pandas"] = pandas.__version__
    except Exception as e:  # noqa: BLE001
        out["numpy/pandas"] = f"MISSING ({type(e).__name__})"
    try:
        import talib  # type: ignore

        out["talib"] = f"{talib.__version__} / {len(talib.get_functions())} 函数"
    except Exception as e:  # noqa: BLE001
        out["talib"] = f"MISSING ({type(e).__name__})"
    try:
        import czsc  # type: ignore

        out["czsc"] = getattr(czsc, "__version__", "?")
    except Exception as e:  # noqa: BLE001
        out["czsc"] = f"MISSING ({type(e).__name__})"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="个股分析开工前接口巡检")
    ap.add_argument("--code", default="600150", help="6 位代码，可带 sz/sh 前缀（会自动剥）")
    ap.add_argument("--root", default=".", help="工作区根目录（需含 common/tdx_src.py）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    a = ap.parse_args()

    code, stripped = strip_prefix(a.code)
    root = Path(a.root).resolve()

    sdb = probe_stockdb(code)
    tdx = probe_tdx(code, root)
    jev = probe_jev(root)
    env = probe_env()

    dates = [d for d in (sdb.get("last"), tdx.get("last")) if d]
    data_as_of = max(dates) if dates else None

    result = {
        "code": code,
        "stripped_prefix": stripped,
        "dataAsOf": data_as_of,
        "sources_agree": bool(sdb.get("last") and tdx.get("last") and sdb["last"] == tdx["last"]),
        "stockdb": sdb,
        "easy_tdx": tdx,
        "jev": jev,
        "env": env,
        "python": sys.executable,
    }

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        W = 12

        def row(k, v, ok=None):
            mark = "" if ok is None else ("✅" if ok else "❌")
            print(f"  {k:<{W}} {mark:<2} {v}")

        print(f"\n接口巡检 · {code}" + (f"（已剥前缀 {stripped}）" if stripped else ""))
        print("─" * 68)
        if sdb["ok"]:
            row("stockdb", f"{sdb['rows']} 根 | 最新 {sdb['last']} | 收 {sdb['close']} | {sdb['ms']}s", True)
        else:
            row("stockdb", sdb.get("err", "失败"), False)
        if tdx["ok"]:
            row("easy-tdx", f"最新 {tdx['last']} | 收 {tdx['close']} | 行业 {tdx['industry']}", True)
        else:
            row("easy-tdx", tdx.get("err", "失败"), False)
        row("Jev", ("凭据已配置" + (" …" + jev["key_tail"] if jev.get("key_tail") else "")) if jev["ok"] else jev.get("err", "失败"), jev["ok"])
        row("环境", " | ".join(f"{k} {v}" for k, v in env.items()))
        print("─" * 68)
        row("dataAsOf", str(data_as_of) if data_as_of else "未知", bool(data_as_of))
        if sdb.get("last") and tdx.get("last"):
            row("两源一致", "是" if result["sources_agree"] else f"否（stockdb {sdb['last']} / tdx {tdx['last']}）",
                result["sources_agree"])
        if not sdb["ok"] and not tdx["ok"]:
            print("\n⛔ 两个行情源都不可用 —— 停止，不要用旧缓存或占位值硬跑。")
        elif not sdb["ok"]:
            print("\n⚠️ stockdb 不可用：可降级 easy-tdx，但大批量历史取数会受限，须在报告标注。")
        if not jev["ok"]:
            print("⚠️ Jev 不可用：报告必须显式写「本版未含语义判断层」，不得默默省略。")

        print("\n提示：Python 必须是托管 venv —— 系统 python 没有 numpy/pandas/talib。")
        print("      C:\\Users\\mai_k\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe\n")

    if not sdb["ok"] and not tdx["ok"]:
        return 2
    if not sdb["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
