# CI/CD 与发布手册 — snippin（T-19 / T-17）

- 负责人：DevOps 工程师（CD）；发布批准：项目经理（PJM）
- 本文是 `.github/workflows/*.yml`、`packaging/snippin.spec`、`packaging/build_exe.bat`
  里多处引用的那一份文档（此前缺失，实现说明与门禁口径在此统一）
- 相关风险：`docs/RISKS.md` R-04（杀软误报）、R-08（未经真机验证）、R-09/R-10（OCR 依赖系统能力）、R-11（翻译联网）

## 1. 流水线全貌

```text
PR / push(main,develop)
  ├─ lint         ruff==0.17.0，ubuntu            ┐
  ├─ test         pytest 3.10/3.11/3.12，windows  ├─ 必需 → ci-gate（分支保护只勾这一条）
  └─ build-exe    PyInstaller onedir + 体积核查    ┘
  └─ hygiene      密钥扫描 + pip-audit            ── 建议项（advisory），不进门禁

push tag v*  → Release：版本一致性校验 → 打包 → 冒烟 → 体积核查 → zip+SHA256
                          → 构建出处证明 → GitHub Release（自动 changelog）
workflow_dispatch → 同一套流程的「干跑」：构建与校验全跑，但不创建 Release
```

配置事实：

| 项 | 取值 | 为什么 |
| --- | --- | --- |
| runner | `windows-latest`（test/build）、`ubuntu-latest`（lint/hygiene） | 产品目标是 Windows（R-03），Qt/热键/打包行为要与用户环境一致，不用 offscreen 变通 |
| ruff | 锁 `0.17.0`；规则集在 `pyproject.toml` 显式声明 | 双保险：锁版本防行为漂移，显式 `select` 防默认规则集扩张 |
| PyInstaller | 锁 `6.22.3`（CI 与 Release 同一 env） | 包内文件构成与杀软误报率随版本变化，升级必须走依赖 PR |
| 密钥 | **零**。workflow 只引用默认只读 `GITHUB_TOKEN`；签名 secrets 仅以名字出现 | 公开仓库；见第 6 节 |

## 2. 分支保护：只勾 `ci-gate`

必需检查选 `ci-gate` 这一条聚合项即可。矩阵作业名（`test (3.10)` 等）会随列增减变化，
逐个设为必需检查会让保护规则长期处于待维护状态。

**启用前置条件：`ci-gate` 目前不能开启** —— `pytest` 在 HEAD 有 1 个失败用例
（选区反向拖拽少 1 像素，见 Issue #2）。基线红的时候设必需检查，会拦住所有无关 PR。
修复合入后再开。具体建议清单（含 `gh api` 命令与回滚命令）见本文第 7 节。

建议项失败**不拦截合并，但要求 PR 里回应**（PR 模板已写入该条），尤其 `hygiene` 报疑似密钥时必须立刻处理。

## 3. 体积核查（把「OCR 增量为 0」变成能执行的闸）

架构承诺：文字提取走 **Windows 系统 OCR（Windows.Media.Ocr）**，不随包分发任何模型或引擎二进制，
因此打包体积增量应为 0；翻译走在线 API，不应引入大依赖。
口头承诺挡不住一次「顺手加个 easyocr」的 PR，所以落成两道闸（`packaging/check_size.py` + `packaging/size-budget.json`）：

1. **上限闸**：产物超过 `max_bytes` 即失败。当前 onedir 基线 82.9 MiB，上限 92 MiB（约 +11% 余量）。
2. **依赖闸**：扫描包内条目，命中 `tesseract / paddle / easyocr / onnx / torch* / tensorflow /
   keras / transformers / cv2 / ultralytics` 或 `.traineddata / .onnx / .pt / .safetensors` 即失败。
   这条不只是体积问题——引入本地 OCR 模型同时违反「图片不出本机」的隐私承诺。

`winrt / PIL / numpy` 在 `watch_patterns` 里：**不拦截，只在报告点名**。
系统 OCR 的 winrt 绑定体积极小但并非严格为 0，出现时要求 PR 描述给出实测增量，而不是假装它是 0。

核查结论写入 Job Summary，reviewer 不用翻日志。本地同命令：

```bash
python packaging/check_size.py --mode onedir --report
```

门禁有效性做过负向验证（能失败才算门禁）：压低上限 → `exit 1`；
把已存在的 DLL 名注入 `forbidden_patterns` → `exit 1`。

### DLL 层裁剪（本次增量，实测依据）

`snippin.spec` 的 `excludes` 只作用于 Python 模块解析，**挡不住 PySide6 hook 按插件依赖把 DLL 拉回包内**。
用现网 spec 在 Python 3.12.10 / PySide6 6.12.0 / PyInstaller 6.22.3 实测：

| 包内文件 | 体积 | 仅 excludes 时 |
| --- | --- | --- |
| `opengl32sw.dll` | 19.68 MiB | 仍在包内 |
| `Qt6Quick.dll` | 6.44 MiB | 仍在包内 |
| `Qt6Qml.dll` | 5.14 MiB | 仍在包内 |
| `Qt6Pdf.dll` | 4.41 MiB | 仍在包内 |
| `Qt6QmlModels.dll` | 0.97 MiB | 仍在包内 |
| `Qt6VirtualKeyboard.dll` | 0.40 MiB | 仍在包内 |
| **合计** | **37.1 MiB（占整包 31%）** | 119.9 MiB → 裁剪后 **82.9 MiB** |

裁剪后保留：`platforms/qwindows.dll`、`platforms/qdirect2d.dll`、`imageformats/*`（PNG/JPEG 保存）、
`Qt6Network` + `libssl/libcrypto`（在线翻译 provider 的 TLS 能力）。

⚠ **残留风险（需 T-12 覆盖）**：裁掉 `opengl32sw.dll` 后，无 GPU / 基本显示驱动 / 虚拟机环境的
渲染表现未经验证。请在手动矩阵补一列「1366×768 虚拟机 + 基本显示驱动」的启动与框选验证。
出问题时设 `SNIPPIN_PKG_PRUNE=0` 即完全还原未裁剪包，不需改代码。

## 4. 杀软误报对策（R-04）

误报成因在本项目可枚举：无签名的 PyInstaller exe、`keyboard` 库的全局键盘钩子、onefile 的临时目录自解压。

| 措施 | 状态 | 说明 |
| --- | --- | --- |
| onedir 而非 onefile 分发 | **已落地**（既有决策） | 不自解压、不落临时 exe；启动也快，兼顾热键即截体验 |
| 禁用 UPX | **已固化**（`upx=False`） | UPX 外壳是误报头号诱因 |
| exe 写入产品名/公司/版本元数据 | **已落地**（`make_version_info.py`） | 「无元数据」是启发式误报的常见加分项 |
| 单一版本源 + tag 一致性校验 | 已落地（release.yml） | 避免发出与源码不符的包 |
| 构建出处证明（attestation） | 已落地（release.yml） | 供应链透明，用户可验证产物确实来自本仓库 CI |
| CI 冒烟启动 exe | 已落地（release.yml，offscreen 8 秒不退出 + 检查 qwindows.dll） | 把「打包成功」和「能起进程」分开证明 |
| 锁定 PyInstaller 版本 | 已落地 | 行为可复现，厂商白名单才可能积累信誉 |
| 源码运行路径 | 已在 README | `pip install -e .` + `python -m snippin` |
| 全局钩子的用途说明 | **待办（UI/文档）** | README 与设置面板必须明写：钩子只用于唤起截图、不记录按键内容。既是信任问题，也影响厂商判定 |
| 提交误报申诉 | 待办（发布前） | 向 Microsoft 及主流厂商提交；准备好上面的行为说明 |
| 代码签名 | **需 PM 批准**，见第 6 节 | 当前流水线不签名，也不假装签名 |
| 不做的事 | — | 不为过杀软做混淆/加壳；不关闭实时保护来「验证」；不偷偷改钩子行为 |

## 5. 版本号、tag 与 changelog

- **单一版本源**：`src/snippin/__init__.py::__version__`；
  `pyproject.toml` 用 `dynamic = ["version"]` 读取它，exe 版本资源与 Release 名同源。
- tag 形式：`vX.Y.Z`，预发布 `vX.Y.Z-rc.1`。
- **发布顺序不可颠倒**：先改 `__version__` 并合入 `main`，再对该提交打 tag。
  release.yml 会比对 `v$__version__` 与 tag，不一致直接抛错。
- 里程碑：M1 冒烟可用 `0.1.x` → M2 功能齐备 `0.2.x` → M3 公开发布 `1.0.0`（首次稳定承诺）。
- changelog：现用 `gh release create --generate-notes`。
  若要按 Conventional Commits 归段（新功能/缺陷修复/打包/工程化…）并自动附上
  「OCR 语言包」「翻译密钥需本机配置」两条前置条件，可用 `packaging/gen_changelog.py`（本增量附带）。

发布物：`snippin-<版本>-win64.zip` + `SHA256SUMS.txt`（Windows 侧 `Get-FileHash` 可对照）。

## 6. 代码签名评估

结论：**M3 发布前不签名**，但保留接入路径。当前无可用证书，自签名对 SmartScreen 无帮助且增加混淆。

| 方案 | 成本 | 评价 | 障碍 |
| --- | --- | --- | --- |
| SignPath.io（OSS 免费，Azure Trusted Signing 后端） | 免费（需资格） | 最推荐 | 项目需过其开源资格审核；CI 接其作业流 |
| Azure Trusted Signing | 约 $10/月 | 可行 | 要求组织域名持有满 3 年 + 组织验证 |
| 商业 OV/EV 证书 | 数百至数千美元/年 | 长期最优 | 费用、私钥托管、EV token 不可安全放入 CI |

启用步骤（PM 批准后由 CD 执行）：

1. 仓库 Settings → Secrets and variables → Actions 里只配**名字**，值不进仓库：
   `SIGNPATH_PROJECT_SLUG`、`SIGNPATH_API_TOKEN`（命名先与 PM 确认，避免同义重复）。
2. 在 release.yml 增加签名步骤：先检测 secrets 是否存在，未配置则整步跳过；
   **已配置但签名动作未接线时让流水线报错退出** —— 防止「以为签了其实没签」这种最危险的静默失败。
3. 只签 `snippin.exe` 本体（onedir 内部 DLL 不逐个签）。
4. Release 说明里同时给出签名前后的 SHA-256 对照。

红线：不提交 `.pfx`；不在 workflow 明文写证书口令；不在本地脚本硬编码 token。

## 7. 发布与回滚

### 正常发布

```text
main 合入 → 改 __version__ 的 PR（ci-gate 绿）→ 合入 → 打 tag → Release 流水线自动出包并发布
```

人工确认三件事：两个下载链可用、本机跑通「热键唤起 → 框选 → 保存 → 贴图」、SHA-256 对得上。
发布前可先 `workflow_dispatch` 干跑一次，只构建不发布。

分支保护配置（管理员执行，不由 CI 自动改，避免自我授权）：

```bash
gh api -X POST repos/fenglangyj/snippin/branches/main/protection \
  -H "Accept: application/vnd.github+json" --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["ci-gate"] },
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true },
  "enforce_admins": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

验证：`gh api repos/fenglangyj/snippin/branches/main/protection --jq .required_status_checks.contexts`
→ `["ci-gate"]`。撤销：`gh api -X DELETE repos/fenglangyj/snippin/branches/main/protection`。

建议同时配置：CODEOWNERS（`ocr/base.py`、`translate/base.py` 归 BE；`.github/workflows/`、`packaging/` 归 CD）、
Dependabot alerts + secret scanning（公开仓库免费）、以及三个 Issue 模板用到的 labels。

### 回滚（三类，代价差别很大，先判类型）

**A. 发布物有问题、代码没问题**（打包/裁剪导致启动失败）

```bash
gh release edit vX.Y.Z --latest=false      # 让上一版重新成为 Latest
gh release view vPREV --json url           # 确认下载地址
```

上一条 Release 的资产不会被删除，无需重新出包。在 Issue 置顶「请暂用 vPREV」。

**B. 代码有问题**（功能缺陷）

1. 提 revert PR：`git revert -m 1 <merge-sha>` 或 `git revert <sha>`；
2. `ci-gate` 绿后合入，打**更高补丁号** `vX.Y.(Z+1)` 发布修复版；
3. 旧版标记：`gh release edit vX.Y.Z --prerelease --latest=false`，说明开头写「⚠ 此版本存在 <缺陷>」；
4. **不删 Release、不删 tag**：已有用户装着它，删除等于销毁取证材料。main 历史禁止 force push。

**C. 隐私/安全事件**（图像误传、密钥入库）

1. 立刻 `gh release edit` 撤下 Latest，停止分发；
2. 密钥一旦推送即**视为已泄露**：通知 PM 与用户撤销/轮换；清历史需 force push，默认禁止，须 PM 单独批准；
3. 在 `docs/RISKS.md` 升级对应风险并出事故记录。

回滚后验证清单：exe 启动 → 托盘图标出现 → 热键唤起遮罩 → 框选保存 → 贴图显示；
`python packaging/check_size.py --mode onedir` 仍在预算内。

## 8. 残留风险

- 未签名：SmartScreen「未知发布者」短期不会消失，R-04 只做到缓解。
- `opengl32sw.dll` 裁剪后的极端环境表现未验证（等 T-12）。
- CI 依赖 GitHub 公开仓库的免费 Windows runner 额度；若转私有或额度受限需改自托管 runner（先与 PM 确认权限边界）。
- winrt 系统 OCR 绑定（T-21）尚未实现，出包后的真实增量需回填 `size-budget.json` 的说明字段。
- 体积预算基线是在 T-19 工作副本的 src 上测得，未含 T-02/T-26 的 theme/assets；首次 CI 跑通后应以 CI 实测值回填，而不是放宽余量。
