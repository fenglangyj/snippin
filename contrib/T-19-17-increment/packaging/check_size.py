"""打包体积核查（T-17）.

把 PRD 里「OCR 走 Windows 系统 API，因此打包体积增量应为 0」这条架构承诺
变成可执行的回归防线：

1. 体积上限：产物超过 `packaging/size-budget.json` 的 `max_bytes` 即失败；
2. 重量级依赖检测：包内出现 OCR/ML 重型库或模型文件即失败（这类依赖一旦进来，
   体积承诺立刻失效，且与「图片不出本机」的隐私承诺冲突）；
3. 构成明细：输出各组件占用，让 reviewer 看得见增量来自哪里。

用法：
    python packaging/check_size.py --mode onefile --report
    python packaging/check_size.py --mode onedir --dist dist

退出码：0 通过；1 超预算或命中禁止依赖；2 产物缺失/参数错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

# 命中即失败：引入这些依赖意味着不再使用 Windows 系统 OCR（R-09/R-10 的架构前提被推翻），
# 或翻译改成了本地大模型（与 PRD 的在线 API 方案冲突）。
FORBIDDEN = [
    r"^tesseract",
    r"^paddle",
    r"^easyocr",
    r"^onnx",
    r"^torch",
    r"^torchvision",
    r"^tensorflow",
    r"^keras",
    r"^transformers",
    r"^cv2",
    r"^ultralytics",
    r".*\.traineddata$",
    r".*\.onnx$",
    r".*\.pt$",
    r".*\.safetensors$",
]

# 需要单独盯住的可选项：winrt/projection 是系统 OCR 的绑定层，体积小但非零，
# 出现时必须在 PR 里说明增量。
WATCH = [r"^winrt", r"^pywinrt", r"^Windows$", r"^windows_"]


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            f = Path(root) / name
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def _bundle_entries(mode: str, exe: Path, onedir_root: Path) -> list[str]:
    """返回包内条目名（onefile 读 CArchive TOC，onedir 读目录树）。"""
    if mode == "onedir":
        return [str(p.relative_to(onedir_root)).replace("\\", "/") for p in onedir_root.rglob("*") if p.is_file()]
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        print("::warning:: 未安装 PyInstaller，跳过 onefile 包内条目扫描（仅核体积）。")
        return []
    try:
        return list(CArchiveReader(str(exe)).toc.keys())
    except Exception as exc:  # 读取失败不应误判为体积违规
        print(f"::warning:: 读取 onefile 归档失败（{exc}），跳过包内扫描。")
        return []


def _classify(entry: str) -> str:
    name = entry.lower()
    if "pyside6" in name or name.endswith(("qt6core.dll", "qt6gui.dll", "qt6widgets.dll")):
        return "PySide6/Qt"
    if name.startswith("_bootstrap") or "base_library" in name or name.endswith(".pyd") and "python" in name:
        return "python 运行时"
    if name.endswith((".pyc", ".py")):
        return "python 字节码/模块"
    return "其他"


def _match(entries: list[str], patterns: list[str]) -> list[str]:
    rx = [re.compile(p, re.I) for p in patterns]
    return sorted({e for e in entries for r in rx if r.search(os.path.basename(e)) or r.search(e)})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="snippin 打包体积核查")
    ap.add_argument("--mode", choices=["onefile", "onedir"], default="onefile")
    ap.add_argument("--dist", default="dist", help="产物目录（默认 dist）")
    ap.add_argument("--budget", default=None, help="预算文件，默认 packaging/size-budget.json")
    ap.add_argument("--report", action="store_true", help="把结论写入 $GITHUB_STEP_SUMMARY")
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    budget_file = Path(args.budget) if args.budget else repo / "packaging" / "size-budget.json"
    dist = Path(args.dist)

    exe = dist / "snippin.exe"
    onedir_root = dist / "snippin"
    if args.mode == "onefile":
        target, exists = exe, exe.is_file()
    else:
        target, exists = onedir_root, onedir_root.is_dir()
    if not exists:
        print(f"::error::未找到 {args.mode} 产物：{target}")
        return 2

    if not budget_file.is_file():
        print(f"::error::缺少体积预算文件：{budget_file}（应由 PR 显式修改，勿自动生成）")
        return 2
    budget_doc = json.loads(budget_file.read_text(encoding="utf-8"))
    # 体积上限按形态放在 mode 子字典里；规则列表在顶层（两种形态共用）。
    # 取错层级会让 size-budget.json 里声明的规则被静默忽略，只跑内置默认值。
    budget = budget_doc[args.mode]
    forbidden_patterns = budget_doc.get("forbidden_patterns", FORBIDDEN)
    watch_patterns = budget_doc.get("watch_patterns", WATCH)

    size = exe.stat().st_size if args.mode == "onefile" else _dir_size(onedir_root)
    max_bytes = int(budget["max_bytes"])
    baseline = int(budget.get("baseline_bytes", max_bytes))

    entries = _bundle_entries(args.mode, exe, onedir_root)
    forbidden_hits = _match(entries, forbidden_patterns)
    watch_hits = _match(entries, watch_patterns)

    by_class: Counter[str] = Counter()
    for e in entries:
        by_class[_classify(e)] += 1

    lines: list[str] = []
    lines.append(f"- 形态：**{args.mode}**  产物：`{target.name}`")
    lines.append(f"- 体积：**{size / 1048576:.1f} MiB** / 上限 {max_bytes / 1048576:.1f} MiB"
                 f"（基线 {baseline / 1048576:.1f} MiB，增量 {(size - baseline) / 1048576:+.1f} MiB）")
    lines.append(f"- 包内条目：{len(entries) or '未扫描'}；构成：{_dict_str(by_class)}")
    if watch_hits:
        lines.append(f"- ⚠ 需说明的可选依赖命中：{', '.join(watch_hits[:8])}"
                     "（系统 OCR 绑定层体积小但非零，请在 PR 描述里给出增量）")
    if forbidden_hits:
        lines.append(f"✗ 命中禁止依赖：{', '.join(forbidden_hits[:8])}")

    print("\n".join(lines))

    ok = True
    if size > max_bytes:
        print(f"::error::体积超预算：{size} > {max_bytes} bytes。"
              "若为必要增长，请在 PR 中修改 packaging/size-budget.json 并说明理由与增量来源。")
        ok = False
    if forbidden_hits:
        print("::error::包内出现重量级 OCR/ML 依赖或模型文件，"
              "违反「OCR 走 Windows 系统 API、图片不出本机」的架构承诺。")
        ok = False

    if args.report:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("## 体积核查（" + args.mode + "）\n\n" + "\n".join(lines) + "\n\n"
                         + ("**结论：通过**\n" if ok else "**结论：未通过**\n"))

    return 0 if ok else 1


def _dict_str(counter: Counter[str]) -> str:
    if not counter:
        return "（无）"
    return "，".join(f"{k} {v} 项" for k, v in counter.most_common(4))


if __name__ == "__main__":
    raise SystemExit(main())
