# release.yml 增量片段：把「体积报告」升级为「报告 + 门禁」

现状：`release.yml` 的 *体积报告（写入 Job Summary）* 步骤只打印数字，不判断，
所以一次引入本地 OCR 模型的提交可以一路走到 Release。
下面两步替换/追加在原步骤位置即可，其余步骤（版本校验、冒烟、zip+SHA256、
attestation、Release 创建）**保持原样不动**，那几处比我的初版做得好。

## 1. 替换原「体积报告」步骤

```yaml
      - name: 体积核查（报告 + 门禁：上限与重量级依赖双闸）
        shell: pwsh
        run: |
          python packaging\check_size.py --mode onedir --report
          if ($LASTEXITCODE -ne 0) { throw "体积核查未通过：见上方结论与 packaging/size-budget.json" }
```

`check_size.py` 自己会把结论写进 `$GITHUB_STEP_SUMMARY`（`--report`），
因此 Job Summary 的呈现与原步骤一致，只是多了一条硬结论。

## 2. 紧随其后追加构成明细（可选，但强烈建议）

裁剪清单一旦改动，需要能立刻看出哪个 DLL 回来了：

```yaml
      - name: 包内最大的 10 个文件
        shell: pwsh
        run: |
          $root = (Get-Location).Path.Length + 1
          "### 包内 Top 10" | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
          Get-ChildItem dist\snippin -Recurse -File |
            Sort-Object Length -Descending | Select-Object -First 10 |
            ForEach-Object { ("- {0} — {1:N2} MiB" -f $_.FullName.Substring($root), ($_.Length / 1MB)) } |
            Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8
```

## 3. 干跑（workflow_dispatch）也应触发体积核查

`check_size` 步骤本身不在 `if: github.ref_type == 'tag'` 条件内，所以干跑会一并执行 —— 这正是
「发布前预演 + 体积核查」的用途，无需额外改动。若想更严格，可在 `preflight` 类步骤里补一条：
tag 触发时校验 tag 与 `src/snippin/__init__.py::__version__` 一致（原 workflow 已有，保持）。

## 4. 依赖前置

- 需要仓库内存在 `packaging/check_size.py` 与 `packaging/size-budget.json`（本增量已提供）。
- `check_size.py` 只依赖标准库，`onedir` 模式走目录遍历，不需要 PyInstaller 的归档读取器；
  `onefile` 模式才用 `PyInstaller.archive.readers`（release 里已装 PyInstaller，无新增依赖）。
