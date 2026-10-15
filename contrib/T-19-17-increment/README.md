# T-19 / T-17 增量交付（以现网 CI/打包实现为基底）

## 背景：为什么不是一套全新实现

同一批任务在 `Z:\Project\Agent\snippin` 已有一套**正在进行的实现**
（`.github/workflows/ci.yml`+`release.yml`、dependabot、Issue/PR 模板、
`packaging/snippin.spec`、`make_version_info.py`、onedir 版 `build_exe.bat`，均未提交）。
我这边的独立实现已全部本地验证并停在分支 `feature/T-19-17-ci-cd`（未推送）。

两套并推会开出正面重复的 PR，对团队是净损失。**按拍板结论：以现网那套为基底，这里只交增量。**

现网实现在三处比我的初版好，我已放弃自己的版本、改按它的口径重写增量：

| 分歧点 | 现网选择（采纳） | 我原方案（作废） |
| --- | --- | --- |
| 分发形态 | **onedir 唯一**：启动快（热键即截体验）、误报率低 | onefile 主 + onedir 备选 |
| 版本源 | `src/snippin/__init__.py::__version__` + pyproject `dynamic` | `pyproject [project] version` 静态 |
| Release 能力 | 构建出处证明 attestation、**CI 内冒烟启动 exe**、干跑预演、PyInstaller 锁版本 | 仅 tag 校验 + SHA256 |

尤其第三条：现网 release.yml 已经在 runner 里用 offscreen 启动 exe 跑 8 秒并检查
`qwindows.dll` 是否齐全 —— 这解决了「打包成功 ≠ 进程能起」的空白，比我在开发机上试探更合适。

## 增量清单（8 个文件）

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `packaging/snippin.spec` | **替换** | 在现网 spec 上加 DLL 层裁剪（`PRUNE_BINARIES`）；`excludes` 清单、图标、版本元数据、`upx=False` 全部原样保留 |
| `packaging/check_size.py` | **新增** | 体积双闸：上限 + 重量级 OCR/ML 依赖与模型文件；结论写 Job Summary |
| `packaging/size-budget.json` | **新增** | onedir 基线 82.9 MiB / 上限 92 MiB，含实测出处与裁剪说明；`winrt/PIL/numpy` 为 watch 不拦截 |
| `.github/workflows/ci.yml` | **替换** | 保留 lint/test 原样（步骤名、`ruff==0.17.0`、`--output-format=github`、offscreen、矩阵），新增：lint 覆盖 `packaging/`、pytest junit 报告、`build-exe` 作业（PR 就出包+体积核查+给 T-12 传构建物）、`hygiene` 建议项、`ci-gate` 聚合 |
| `.github/ISSUE_TEMPLATE/contract_change.yml` | **新增** | 冻结契约变更专用模板（现有只有 bug/feature）；要求说明兼容性影响与是否触及隐私/体积承诺 |
| `docs/CI_CD.md` | **新增** | **现网 spec、release.yml、build_exe.bat 三处引用了它但文件不存在**。补齐：流水线全貌、分支保护、体积核查与裁剪实测、R-04 对策表、签名评估、发布与三类回滚 |
| `docs/release-yml-snippet.md` | **片段** | release.yml 的改动仅此一处：体积报告 → 报告+门禁（附 Top10 明细）。不整份替换，避免覆盖 attestation/冒烟等更好实现 |
| `packaging/gen_changelog.py` | **可选新增** | 若要替掉 `--generate-notes`，按 Conventional Commits 归段并自动附「OCR 语言包 / 翻译密钥」前置条件 |

应用方式：前 5 项直接复制覆盖/放入同名路径；release.yml 按片段文档改一步；`docs/CI_CD.md` 放好后
把三处引用的链接确认一遍。

## 支撑数据（都用真实构建量出来的，不是估的）

- **裁剪必要性实测**：用**现网那份 spec** 构建 onedir → `119.9 MiB / 213 文件`，
  其中 `opengl32sw.dll 19.68`、`Qt6Quick 6.44`、`Qt6Qml 5.14`、`Qt6Pdf 4.41`、
  `Qt6QmlModels 0.97`、`Qt6VirtualKeyboard 0.40` **六个 DLL 全部仍在包内**，
  合计 37.1 MiB（31%）。原因：`excludes` 只管 Python 模块解析，PySide6 hook 会按插件依赖把 DLL 拉回来。
  加裁剪后 → `82.9 MiB / 207 文件`。
- **门禁可失败性验证**：把上限压到 1 MiB → `exit 1`；把包内确实存在的 `Qt6Core.dll` 注入
  `forbidden_patterns` → `exit 1` 并点名该文件。能失败才叫门禁。
- 顺手修掉自己写出的两个真 bug：`forbidden_patterns` 从 JSON 的 mode 子字典里读（层级错，
  会让文件里声明的规则被静默忽略）；`gen_changelog.py` 残留已删除函数的调用（会 NameError）。
- 全部 workflow 已扫描：只出现 secret **名字**，零密钥值。

## 需要接手方注意的两点

1. **`ci-gate` 现在不能设为必需检查** —— `pytest` 在 HEAD 有 1 个失败用例（选区反向拖拽少 1 像素），
   我已提 [Issue #2](https://github.com/fenglangyj/snippin/issues/2) 并附实测证据与建议改法。
   基线红的时候设必需检查会拦住所有无关 PR；修复合入后再开。
2. **裁剪引入的验证缺口**：`opengl32sw.dll` 被移除后，虚拟机/基本显示驱动环境的渲染未验证，
   需 T-12 手动矩阵补一列。兜底开关：`SNIPPIN_PKG_PRUNE=0` 不改代码即可还原。

`feature/T-19-17-ci-cd` 分支上另有我已验证但我方不再需要的完整实现
（含独立 release.yml、onefile 预算、`docs/BRANCH_PROTECTION.md`），可作为对照材料，
若某处现网实现缺件可从那里取。
