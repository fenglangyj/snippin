"""按 Conventional Commits 生成 Release 说明（T-17）.

用法：
    python packaging/gen_changelog.py --tag v0.1.0 --from v0.0.9 --out CHANGELOG.md
    python packaging/gen_changelog.py --tag v0.1.0 --from "" --out CHANGELOG.md   # 首个版本

约定：
- 段落标题用中文，条目保留提交的原始描述（中英混排不做翻译）；
- 未遵循 Conventional Commits 的提交归入「其他」并在 stderr 计数，
  提醒发布负责人是否需要在 Release 说明里手工补充。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict

SECTIONS: list[tuple[str, str]] = [
    ("feat", "新功能"),
    ("fix", "缺陷修复"),
    ("perf", "性能"),
    ("refactor", "重构"),
    ("docs", "文档"),
    ("test", "测试"),
    ("build", "打包"),
    ("ci", "工程化"),
    ("revert", "回滚"),
    ("other", "其他"),
]

PREFIX = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$")


def _git(ref_range: str) -> list[str]:
    out = subprocess.run(
        ["git", "log", ref_range, "--no-merges", "--pretty=format:%s"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def build(tag: str, prev: str) -> tuple[str, int]:
    rng = f"{prev}..HEAD" if prev else "HEAD"
    subjects = _git(rng)
    buckets: dict[str, list[str]] = defaultdict(list)
    breaking: list[str] = []
    irregular = 0

    for subject in subjects:
        m = PREFIX.match(subject)
        if not m:
            buckets["other"].append(subject)
            irregular += 1
            continue
        ctype = m.group("type")
        key = ctype if ctype in dict(SECTIONS) else "other"
        if ctype == "chore":
            key = "other"
        scope = m.group("scope")
        text = f"**{scope}**: {m.group('desc')}" if scope else m.group("desc")
        entry = text
        buckets[key].append(entry)
        if m.group("bang"):
            breaking.append(entry)

    lines = [f"## {tag}", ""]
    if prev:
        lines.append(f"相较于 {prev} 的改动（{len(subjects)} 个提交）。")
    else:
        lines.append("首个公开版本。")
    lines.append("")

    if breaking:
        lines.append("### ⚠ 破坏性变更")
        lines += [f"- {b}" for b in breaking]
        lines.append("")

    title_map = dict(SECTIONS)
    for key, _ in SECTIONS:
        items = buckets.get(key)
        if not items:
            continue
        lines.append(f"### {title_map[key]}")
        lines += [f"- {i}" for i in items]
        lines.append("")

    lines += [
        "### 安装与运行",
        "",
        "- `snippin-<版本>.exe`：单文件版，双击即运行（推荐普通用户）。",
        "- `snippin-<版本>-win-x64.zip`：目录版，解压后运行 `snippin/snippin.exe`"
        "（被杀软拦截时优先用这个）。",
        "- 源码运行：`pip install -e .` 后 `python -m snippin`。",
        "- 校验：`SHA256SUMS.txt` 内为各文件的 SHA-256。",
        "",
        "### 已知前置条件",
        "",
        "- 文字提取依赖 Windows 系统 OCR：需在「设置 → 时间和语言 → 语言和区域」"
        "安装对应语言的 OCR 支持包，否则该按钮会给出安装引导。",
        "- 翻译需在设置里自行配置服务商密钥，仓库与安装包内均不含任何密钥。",
        "",
    ]
    return "\n".join(lines), irregular


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成 snippin Release 说明")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--from", dest="prev", default="", help="上一个 tag；留空则统计全部历史")
    ap.add_argument("--out", default="-", help="输出文件，默认 stdout")
    args = ap.parse_args(argv)

    text, irregular = build(args.tag, args.prev)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"已写入 {args.out}")
    if irregular:
        print(f"提示：{irregular} 个提交不符合 Conventional Commits，已归入「其他」", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
