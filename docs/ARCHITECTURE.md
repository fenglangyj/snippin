# 架构说明 — quicksnip

## 1. 总览

单体桌面应用，进程内模块化解耦。核心数据流：

```
热键/托盘触发
   └─> Controller.start_capture()
        └─> capture/grabber.py   跨屏抓屏 -> 一张虚拟桌面大图
             └─> ui/overlay.py   全屏遮罩：框选 -> 标注(编辑态) -> 工具条动作
                  └─> finished(action, image, path)
                       ├─ COPY -> 剪贴板
                       ├─ SAVE -> 文件对话框
                       └─ PIN  -> ui/pin.py 贴图悬浮窗
```

## 2. 模块职责

| 模块 | 职责 | 关键类/函数 |
| --- | --- | --- |
| `app.py` | 进程入口、QApplication、系统托盘、Controller 调度 | `Controller.start_capture/_on_finished` |
| `config.py` | 配置模型与持久化（QSettings） | `Config.next_save_path` |
| `hotkey.py` | 后台全局热键（keyboard 库）+ 线程安全信号 | `HotkeyListener` |
| `capture/grabber.py` | 多屏拼接抓屏 | `grab_virtual_desktop()` |
| `ui/overlay.py` | 遮罩层、选区状态机、工具条、标注编辑 | `Overlay` |
| `ui/pin.py` | 贴图悬浮窗 | `PinWindow` |
| `tools.py` | 标注数据模型 + 绘制（纯数据层，可单测） | `Shape / draw_shape` |
| `utils/geometry.py` | 纯几何计算 | `normalize_rect / arrow_head` |

## 3. 关键设计

- **单一坐标系**：遮罩窗口几何 = 虚拟桌面几何，选区/标注坐标与抓屏图像像素一一对应，渲染输出时仅需平移选区左上角，无缩放换算。
- **状态机**：`select`（按下锚点、拖拽出选区）-> `edit`（工具条出现，绘制标注）-> `done`（`finished` 信号 + 关闭）。点击选区外回到 `select`。
- **马赛克**：抓屏后对整图做一次降采样-还原（FastTransformation），绘制时按目标矩形取对应区域，O(区域) 而非 O(全图)。
- **绘制与数据分离**：`Shape` 为纯数据（dataclass），`draw_shape` 只依赖 QPainter，便于单元测试与新增工具类型。
- **热键降级**：`keyboard` 库不可用时静默降级为托盘菜单触发。

## 4. 扩展点

- 新增标注工具：`Tool/ShapeType` 加成员 + `draw_shape` 加分支 + 工具条加按钮（T 系列任务已排）。
- 设置面板：扩展 `Config` 读写 + 新增对话框（T-15）。
- 历史记录/上传：在 `Controller._on_finished` 增加动作分支即可，overlay 无需改动。

## 5. 已知限制

- Linux：Wayland 下抓屏与全局热键受合成器限制，`keyboard` 库需 root；首版以 Windows 为准。
- 选区暂不支持 8 向手柄调整（M2）；放大镜未实现（M2）。
- 配置暂以代码默认值为准，设置面板在 M2。
- 应用图标暂用系统内置图标，正式图标在 T-18 定稿。
