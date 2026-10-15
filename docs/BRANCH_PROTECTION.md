# main 分支保护与 GitHub 治理建议（T-19）

- 提出人：DevOps 工程师；**执行需要仓库管理员（fenglangyj）或项目经理批准**
- 我未擅自改动仓库设置：分支保护属于共享状态变更，需显式授权后执行。

## 1. 建议配置（Settings → Branches → Branch protection rule for `main`）

| 项 | 建议值 | 理由 |
| --- | --- | --- |
| Require a pull request before merging | ✅ | main 只经 PR 进入 |
| Require approvals | 1（核心目录 2） | 小团队，1 票足够；`ocr/base.py`、`translate/base.py` 等冻结契约走 CODEOWNERS 加严 |
| Restrict who can dismiss pull request reviews | 仅 PM/管理员 | 防止「评审有问题直接 dismiss 掉」 |
| Require status checks to pass | ✅ 只勾 **`ci-gate`** | 见下节 |
| Do not allow bypassing the above settings | ✅（管理员也受限） | 否则保护形同虚设；紧急修热可临时解除并记录 |
| Require branch to be up to date before merging | ✅ | 避免「合并后炸 CI」 |
| Require signed commits | ❌ 暂不开 | 团队尚无 GPG 习惯，先别造成阻塞；后续再评估 |
| Include administrators | ✅ | 一致适用 |
| Allow force pushes | ❌ | 公开项目的 main 历史必须可审计；`docs/RELEASE.md` 的回滚走 revert 而非改写 |
| Allow deletions | ❌ | main 不可删 |

## 2. 必需检查项：只勾一条 `ci-gate`

`.github/workflows/ci.yml` 已把矩阵收敛成一个聚合作业 `ci-gate`（`needs: [lint, test, build]`）。
分支保护里只需要搜索并勾选 **ci-gate**，不必逐个勾选

- `lint`
- `test (py3.10)` / `test (py3.11)` / `test (py3.12)`
- `build-exe (onefile)` / `build-exe (onedir)`

这些子作业名会随矩阵列增减而变化，把它们设为必需检查会让保护规则长期处于需要维护的状态；
聚合项把这个负担消掉了。矩阵各列仍在 PR 页面逐个可见，失败时能定位到具体 Python 版本/形态。

**故意不设为门禁**的作业（设计如此，不是遗漏）：

- `smoke-linux (advisory)`：首版 Windows 优先（R-03），Linux 列需要离屏 Qt 与系统库，
  环境噪声不该拦住功能 PR。
- `hygiene (advisory)`：密钥扫描与 `pip-audit` 会报出存量依赖问题与误报，
  是否升级为门禁由 T-20 的发布检查负责人裁定。
  注意 PR 模板已要求「advisory 失败需在 PR 里回应」，不勾门禁 ≠ 可以无视。
- `ruff format --check`：作为 `lint` 里的 `continue-on-error` 步骤存在。
  当前有 7 个文件未格式化，直接设门禁会让所有 PR 变红；等格式化改动单独合一次后再收紧。

## 3. 启用前置条件（重要）

**`ci-gate` 现在不能设为必需检查** —— 基线 `pytest` 有 1 个失败用例：

```
tests/test_geometry.py::test_normalize_rect_swapped_corners  FAILED
assert rect.left() == 10   →   实际 11
```

这不是测试写错。`normalize_rect` 用 `QRect(a, b).normalized()`，而 Qt 的两点构造把
`bottomRight` 视为**包含**在内，反向拖拽（右下 → 左上）时四边各少 1 像素：

| 输入 | 现状输出 | 期望 |
| --- | --- | --- |
| `QPoint(50,60) → QPoint(10,20)` | `QRect(11,21,39,39)`，right=49/bottom=59 | `left=10 top=20 right=50 bottom=60` |

修复（显式取 min/max，语义与测试一致）：

```python
def normalize_rect(a: QPoint, b: QPoint) -> QRect:
    """返回由两个角点张成的规范化 QRect（左上角不一定来自 a）。"""
    return QRect(QPoint(min(a.x(), b.x()), min(a.y(), b.y())),
                 QPoint(max(a.x(), b.x()), max(a.y(), b.y())))
```

处置顺序：

1. 该缺陷属于抓屏/选区行为（相邻 R-02 DPI 风险），由 **BE/FE 判定并合入**，QA 复核；
   DevOps 不单方面改应用代码。
2. 合入后 `pytest` 全绿 → 勾选 `ci-gate` 为必需检查，保护规则即刻生效。
3. 在此之前 PR 依然会跑完整 CI，只是不强制拦截 —— 结论照常在页面呈现，可人工判读。

## 4. 管理员执行命令（可选，替代网页操作）

确认授权后由管理员执行（**不要**由 CI 自动改，避免自我授权）：

```bash
gh api -X POST repos/fenglangyj/snippin/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci-gate"]
  },
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "enforce_admins": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

验证：`gh api repos/fenglangyj/snippin/branches/main/protection --jq .required_status_checks.contexts`
应输出 `["ci-gate"]`。回滚：`gh api -X DELETE repos/fenglangyj/snippin/branches/main/protection`。

## 5. 仓库其他治理建议

- **CODEOWNERS**（建议由 PM 定稿后加）：
  ```gitignore
  src/snippin/ocr/base.py           @<BE>
  src/snippin/translate/base.py     @<BE>
  .github/workflows/                @<CD>
  packaging/                        @<CD>
  docs/                             @<PJM>
  ```
  冻结契约文件必须有 BE 审核，落实 CONTRIBUTING「契约变更先提 Issue」。
- **Labels**：现有模板用到 `bug / enhancement / contract / needs-review / triage / dependencies / ci`。
  请 PM 在 Issues → Labels 里建好，并配一个 `needs-triage → 周简报` 的流程。
- **Security tab**：启用 Dependabot alerts + secret scanning（公开仓库免费）。
  `.github/dependabot.yml` 已就位（pip 每周一 09:00 Asia/Shanghai，dev 工具合并成一个 PR；github-actions 同频）。
- **仓库描述与主页**：建议 description 写「轻量独立的微信风格截图工具（Windows 优先）」，
  与 README 的 Windows 优先声明一致（R-03/R-10 要求显著声明）。
- **分支模型校正建议**：`CONTRIBUTING.md` 写了 `develop` 集成分支，但仓库当前只有 `main`。
  小团队直接「feature → main」更省事；请 PM 决定是补 `develop` 还是改文档，二选一，别让文档与现实长期不一致。
