# 架构说明 — snippin（快截）

## 1. 总览

单体桌面应用（Python + PySide6），进程内模块化解耦。核心数据流：

```
热键/托盘触发
   └─> Controller.start_capture()                      [app.py]
        └─> capture/grabber.py   跨屏抓屏 -> 虚拟桌面大图
             └─> ui/overlay.py   全屏遮罩：框选 -> 标注 -> 工具条动作
                  ├─ 选区渲染 -> 输出动作
                  │    ├─ COPY -> 剪贴板
                  │    ├─ SAVE -> 文件对话框
                  │    └─ PIN  -> ui/pin.py 贴图悬浮窗
                  ├─ 提取文字 -> ocr/registry.get_engine().recognize(选区图)
                  │    └─ ui/result_panel.py 显示/编辑/复制            [T-22]
                  └─ 翻译     -> translate/registry.get_provider().translate(识别文本)
                       └─ ui/result_panel.py 显示译文与语言选择        [T-24]
```

## 2. 模块职责

| 模块 | 职责 | 关键类/函数 |
| --- | --- | --- |
| `app.py` | 进程入口、QApplication、系统托盘、Controller 调度 | `Controller.start_capture/_on_finished` |
| `config.py` | 配置与密钥存取（QSettings） | `Config.next_save_path / get_translate_secret` |
| `hotkey.py` | 后台全局热键（ctypes WH_KEYBOARD_LL 钩子，零第三方依赖）+ 线程安全信号 | `HotkeyListener / parse_hotkey` |
| `capture/grabber.py` | 多屏拼接抓屏 | `grab_virtual_desktop()` |
| `ui/overlay.py` | 遮罩层、选区状态机、工具条、标注编辑 | `Overlay` |
| `ui/pin.py` | 贴图悬浮窗 | `PinWindow` |
| `tools.py` | 标注数据模型 + 绘制（纯数据层，可单测） | `Shape / draw_shape` |
| `utils/geometry.py` | 纯几何计算 | `normalize_rect / arrow_head` |
| `ocr/base.py` | **冻结契约**：OCR 结果模型与引擎接口 | `OcrEngine / OcrResult / TextBlock / OcrError` |
| `ocr/registry.py` | 引擎注册与选择（懒加载，缺省取首个可用） | `register_engine / get_engine` |
| `ocr/windows.py` | Windows 系统 OCR 引擎实现（T-21） | `WindowsOcrEngine` |
| `translate/base.py` | **冻结契约**：翻译结果模型与服务商接口 | `TranslationProvider / TranslationResult / TranslationError` |
| `translate/registry.py` | provider 注册与选择 | `register_provider / get_provider` |
| `translate/providers.py` | 首个在线翻译服务实现（T-23） | 待实现 |

## 3. 关键设计

- **单一坐标系**：遮罩窗口几何 = 虚拟桌面几何，选区/标注坐标与抓屏图像像素一一对应，输出时仅需平移选区左上角，无缩放换算。
- **状态机**：`select`（锚点拖拽出选区）-> `edit`（工具条出现，绘制标注）-> `done`（`finished(action, image, path)` 信号 + 关闭）。点击选区外回到 `select`。
- **马赛克**：抓屏后对整图做一次降采样-还原（FastTransformation），绘制时只取目标矩形区域，复杂度 O(区域) 而非 O(全图)。
- **绘制与数据分离**：`Shape` 为纯 dataclass，`draw_shape` 只依赖 QPainter，便于单测与新增工具类型。
- **契约先行**：OCR 与翻译的 `base.py` 冻结后，后端实现引擎/provider 与前端实现结果面板可并行开发；新增实现只注册不改契约（`registry.py`）。
- **能力探测而非硬编码**：引擎通过 `available()/unavailable_reason()` 自述可用性，UI 据此给出可读引导（对应 R-09）。
- **热键降级**：钩子注册失败时写入 `HotkeyListener.error`（可感知，不再静默），仍可经托盘菜单触发截图。keyboard 库因在 Python 3.12 下热键匹配失效已移除（缺陷 D-03）。

## 4. 隐私与数据处理

| 功能 | 数据去向 | 说明 |
| --- | --- | --- |
| 截图 / 标注 / 保存 / 贴图 | 完全本机 | 不联网 |
| 文字提取（OCR） | 完全本机 | 调用 Windows.Media.Ocr，图片不出本机，断网可用 |
| 翻译 | 用户主动触发时发送识别文本 | 仅发送文本（不发图片）；服务商由用户选择并自配密钥 |
| 密钥存储 | 本机 QSettings | 不入仓库、不入日志；后续评估 DPAPI 加密（R-12） |

## 5. 扩展点

- 新增标注工具：`Tool/ShapeType` 加成员 + `draw_shape` 加分支 + 工具条按钮。
- 新增 OCR 引擎（如跨平台的 RapidOCR）：实现 `OcrEngine` 并在 `ocr/registry` 注册，UI 无需改动。
- 新增翻译服务商：实现 `TranslationProvider` 并在 `translate/registry` 注册。
- 历史记录 / 图床上传：在 `Controller._on_finished`（及结果面板动作）增加分支即可。

## 6. 已知限制

- 文字提取依赖 Windows 10+ 与系统 OCR 语言包；缺语言包时功能不可用（有引导提示）。
- 翻译需要网络，且翻译质量与配额取决于用户所选服务商。
- Linux/Wayland 下抓屏受限，全局热键钩子仅 Windows 实现（Linux 需另行接入 X11/Wayland 协议）；首版以 Windows 为准。
- 选区暂不支持 8 向手柄调整与放大镜（M2/T-13、T-14）。
- 配置暂以代码默认值 + QSettings 为准，设置面板在 M2（T-15）。
- 应用图标暂用系统内置图标，正式图标在 T-18 定稿。
