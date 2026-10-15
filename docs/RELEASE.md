# 打包与发布手册 — snippin（T-17）

- 负责人：DevOps 工程师（CD）+ 后端工程师（BE）
- 最近更新：2026-10-15
- 相关：`docs/RISKS.md` R-04（杀软误报）、R-09/R-10（OCR 依赖系统能力）、R-11（翻译联网）

## 1. 产物形态

| 形态 | 路径 | 实测体积 | 用途 |
| --- | --- | --- | --- |
| onefile | `dist/snippin.exe` | **32.2 MiB** | 面向普通用户，单文件双击即用 |
| onedir | `dist/snippin/`（发布时压成 zip） | **82.9 MiB** | 杀软误报时的替代分发形态 |

两种形态都由 `packaging/snippin.spec` 一份配置产出，用环境变量切换：

```bat
packaging\build_exe.bat            REM onefile
packaging\build_exe.bat onedir     REM onedir
```

CI（`.github/workflows/ci.yml` 的 `build-exe` 作业）会同时产出两种形态并上传为 PR 构建物，
测试工程师做 T-12 手动矩阵时直接取最新 artifact，不必自己打包。

## 2. 体积核查（把「OCR 体积增量为 0」变成可执行门禁）

这条承诺来自架构决策：文字提取走 **Windows 系统 OCR（Windows.Media.Ocr）**，
不调用任何随包分发的模型或引擎二进制。口头承诺挡不住一次「顺手加个 easyocr」的 PR，
所以由 `packaging/check_size.py` 落成了两道闸：

1. **上限闸**：读 `packaging/size-budget.json` 的 `max_bytes`（onefile 36 MiB / onedir 92 MiB，
   在实测基线上留约 11% 余量）。超限即失败，并提示「增长需在 PR 中改预算并说明理由」。
2. **依赖闸**：扫描包内条目（onefile 读 CArchive TOC，onedir 读目录树），
   命中 `tesseract / paddle / easyocr / onnx / torch* / tensorflow / keras / transformers /
   cv2 / ultralytics` 或 `.traineddata / .onnx / .pt / .safetensors` 文件即失败。
   命中的不只是体积问题——引入本地 OCR 模型同时违反「图片不出本机」的隐私承诺。

另有 `watch_patterns`（`winrt` / `PIL` / `numpy` 等）：**不拦截**，只在报告里点名。
系统 OCR 的 winrt 绑定体积极小但非零，出现时要求 PR 描述里给出实测增量，而不是假装它是 0。

核查结果会写进 CI 的步骤摘要，reviewer 不用翻日志。

```bash
python packaging/check_size.py --mode onefile --report    # 本地同样可跑
```

### 已做的体积裁剪（47.4 → 32.2 MiB，-32%）

只排除 `PySide6.QtXxx` 子模块**并不够**：PySide6 的 PyInstaller hook 会按插件依赖把 DLL 拉回来。
实测后在 spec 里追加了按包内文件名的二次裁剪：

| 裁掉 | 体积 | 理由 |
| --- | --- | --- |
| `opengl32sw.dll` | 19.7 MiB | Qt 软件 OpenGL 回退；本项目只做 QtWidgets 栅格绘制 |
| `Qt6Quick.dll` / `Qt6Qml.dll` / `Qt6QmlModels.dll` | 12.5 MiB | 未使用 QtQuick |
| `Qt6Pdf.dll` | 4.4 MiB | 未使用 QtPdf |
| `Qt6VirtualKeyboard.dll` | 0.4 MiB | 未使用 |

**明确保留**：`platforms/qwindows.dll`、`platforms/qdirect2d.dll`、`imageformats/*`（存 PNG/JPEG）、
`Qt6Network` + `libssl/libcrypto`（在线翻译 provider 的 TLS 能力）。

⚠ 残留风险（需 T-12 覆盖）：裁掉 `opengl32sw.dll` 后，**无 GPU / 基本显示驱动 / 虚拟机**
环境的渲染能力未经验证。请在手动矩阵里补一列「1366×768 虚拟机 + 基本显示驱动」的启动与框选验证。
出问题时把 `SNIPPIN_PKG_PRUNE=0` 设上即可还原为未裁剪包，不需要改代码。

## 3. 杀软误报对策（R-04）

误报的成因在本项目里是可枚举的：无签名的 PyInstaller exe、`keyboard` 库装全局键盘钩子、
onefile 向临时目录自解压。对策按性价比排序：

| 措施 | 状态 | 说明 |
| --- | --- | --- |
| 关掉 UPX 压缩 | **已在 spec 固化**（`upx=False`） | UPX 外壳是误报头号诱因，代价是体积变大，值得 |
| 提供 onedir 形态 | **已落地** | 不自解压、不落临时 exe，检出率显著低于 onefile；Release 同时挂两个包 |
| 源码运行路径 | 已有 | `pip install -e . && python -m snippin`，README 需写明 |
| 固定发布机与可复现构建 | 待办 | 同一 runner 镜像反复出包，有助于厂商白名单积累信誉 |
| 提交误报申诉 | 待办（发布前） | 向 Microsoft / 主流厂商提交误报；准备「全局钩子用途 + 不联网上传图像」的行为说明 |
| 代码签名 | **需 PM 批准**，见下节 | 目前流水线里是「检测 secrets 未配置就跳过」的空步，不会误跑 |
| 不做的事 | — | 不为了过杀软而混淆/加壳、不关闭 Defender 实时保护做验证、不偷偷改 hook 行为 |

补充一条给 UI/文档角色的要求：全局热键是本产品唯一「看起来像键盘记录器」的行为，
README 与设置面板必须明写钩子只用于唤起截图、不记录按键内容。这既是信任问题，也直接影响厂商判定。

## 4. 代码签名方案评估

结论：**M3 发布前不签名，但把签名路径预留在流水线里**。理由是当前没有可用证书，
且自签名证书对 SmartScreen 毫无帮助（反而增加混淆）。三个候选：

| 方案 | 成本 | 适用性 | 障碍 |
| --- | --- | --- | --- |
| **SignPath.io**（开源免费，Azure Trusted Signing 后端） | 免费（OSS 资格） | 最推荐 | 需项目通过其审核；要求 CI 集成其 `sign-path` 作业流 |
| **Azure Trusted Signing** | ~$10/月 | 可行 | 需组织域名持有满 3 年 + 组织验证；个人项目常不达标 |
| 商业 OV/EV 证书（DigiCert/GlobalSign 等） | 数百~上千美元/年 | 长期最优 | 费用、私钥托管、EV token 无法安全放进 CI |

启用步骤（PM 批准后进行，DevOps 执行）：

1. 在仓库 Settings → Secrets and variables → Actions 配置**仅名字**（值不进仓库）：
   `SIGNPATH_PROJECT_SLUG`、`SIGNPATH_API_TOKEN`。命名需与 PM 确认后再建，避免同义重复。
2. 在 `release.yml` 的「代码签名」步骤填入实际的提交/取回逻辑
   （目前该步骤在检测到 secrets 已配置但动作未接入时会**主动报错退出**，防止「以为签了其实没签」）。
3. 签名只作用于 Release 产物，onedir 需签 `snippin.exe` 本体（内部 DLL 不逐个签）。
4. 保留签名前的 SHA-256 与签名后的对照记录在 Release 说明里。

红线：不把证书文件（.pfx）提交进仓库；不把证书密码写进 workflow 明文；
不在本地脚本里硬编码 token。

## 5. 版本号与 tag 规则

- 单一版本源：`pyproject.toml` 的 `[project] version`。
- tag 形式：`vX.Y.Z`，预发布 `vX.Y.Z-rc.1`（语义化版本）。
- **发布顺序不可颠倒**：先改 `pyproject.toml` 版本号并合入 `main`，再对该提交打 tag。
  `release.yml` 的 `preflight` 作业会用 `git describe --tags --exact-match` 比对两者，
  不一致直接失败；同时要求该提交必须在 `origin/main` 上，禁止从分支发布。
- 里程碑对应：M1 冒烟可用 `0.1.x`，M2 功能齐备 `0.2.x`，M3 公开发布 `1.0.0`（首次给出稳定承诺）。
- 打 tag：
  ```bash
  git tag -a v0.1.0 -m "release: v0.1.0"
  git push origin v0.1.0
  ```

## 6. Changelog

`packaging/gen_changelog.py` 按 Conventional Commits 归段（新功能/缺陷修复/性能/重构/文档/测试/打包/工程化/其他），
自动附上「安装与运行」和「已知前置条件」（OCR 语言包、翻译密钥），
这两段是 T-20 发布检查和 R-09/R-10 的落地位置，别在 Release 里手漏。

- 不符合提交规范的 commit 会归入「其他」并在 stderr 计数提醒，不阻塞发布。
- 破坏性提交（`feat!:` / `fix!:`）单独提到「⚠ 破坏性变更」段。
- CI 会把生成结果同时打印到步骤摘要。

发布物清单（Release assets）：`snippin-vX.Y.Z.exe`、`snippin-vX.Y.Z-win-x64.zip`、
`SHA256SUMS.txt`（含每个文件的 SHA-256，Windows 上可用 `Get-FileHash` 对照）。

## 7. 发布流程（正常路径）

```text
main 合入 → 改版本号 PR（含 CHANGELOG 校对）→ 合入 → 打 tag → release.yml 自动出包发布
```

1. 提 PR：仅改 `pyproject.toml` 版本号 + 必要的文档校准，等 `ci-gate` 绿。
2. 合入 `main`，本地 `git pull`。
3. `git tag -a vX.Y.Z -m "release: vX.Y.Z" && git push origin vX.Y.Z`。
4. 打开 Actions → Release，确认：`preflight` → `build (onefile/onedir)` → `publish`。
5. 人工验收 Release 页：两个包都能下载、exe 能在本机启动并截图、SHA-256 对得上。
6. 在周简报记录：版本号、commit、产物体积、已知缺陷列表。

## 8. 回滚方案

回滚分三种，代价差别很大，先判定属于哪一种：

**A. 发布物有问题，但代码没问题**（打包/裁剪导致的启动失败等）
```bash
gh release edit vX.Y.Z --latest=false          # 让上一个版本重新成为 Latest
gh release view vPREV --json url               # 确认下载地址
```
再在 Issue 里置顶说明「请暂用 vPREV」。上一条 Release 的资产不会被删除，因此不需要重新出包。

**B. 代码有问题**（功能缺陷、数据错误）
1. 在 `main` 上提 revert PR：`git revert -m 1 <merge-sha>` 或 `git revert <sha>`（保持可审计，不用 `reset --hard` 改写历史）。
2. `ci-gate` 绿后合入，打**更高的补丁号** `vX.Y.(Z+1)` 发布修复版。
3. 把有问题的 Release 标记：`gh release edit vX.Y.Z --prerelease --latest=false`，
   并在其说明开头加「⚠ 此版本存在 <缺陷>，请勿使用」。
4. **不要删除 Release 或 tag**：已有用户可能装着它，删除会同时销毁取证材料。

**C. 隐私/安全事件**（误传图像、密钥入库）
1. 立即 `gh release edit` 撤下 Latest，停止分发。
2. 密钥若已推送：**视为已泄露**，立刻通知 PM 与用户撤销/轮换。清理 git 历史需要 force push，
   属破坏性操作且对已克隆的副本无效，默认禁止，必须由 PM 单独批准。
3. 在 `docs/RISKS.md` 升级对应风险，产出事故记录。

回滚验证清单（任一形态都要过）：exe 启动 → 托盘图标出现 → 热键唤起遮罩 → 框选保存 → 贴图显示。
体积回到回滚版本的预算内（`python packaging/check_size.py --mode onefile`）。

## 9. 残留风险与待办

- **本次交付的打包产物未经运行验证**：onefile/onedir 两个包均由 CI 同版本 PyInstaller 在本机成功构建、
  体积核查通过，但**没有实际启动过**（启动会注册 Ctrl+Alt+A 全局钩子并显示托盘图标，
  经确认不在开发机上执行）。因此「打包成功」不等于「可用」——`snippin.exe` 能否起窗口、
  框选是否正常，仍需 R-08 要求的各负责人本机 smoke 与 T-12 手动矩阵覆盖。
  `build-exe` 作业只证明「能出包 + 体积合规」，不证明功能可用。
- 未签名：SmartScreen「未知发布者」提示短期不会消失（R-04 只做到缓解，未根除）。
- `opengl32sw.dll` 裁剪后的极端环境渲染表现未知，等 T-12 手动矩阵结论。
- PyInstaller 与 PySide6 版本升级可能改变包内文件构成：体积门禁会拦住异动，但需要人工判读是不是误报。
- winrt 系统 OCR 绑定尚未实现（T-21），出包后其真实体积增量需回填进预算说明。
- CI 目前依赖 GitHub 公开仓库的免费 Windows runner 额度；若仓库转私有或额度受限，需要改为自托管 runner（届时先与 PM 确认权限边界）。
