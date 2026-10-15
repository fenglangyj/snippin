# 贡献指南

感谢你愿意为 quicksnip 贡献代码。本项目按开源协作标准维护，请遵循以下约定。

## 开发环境

要求 Python 3.10+。

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
pytest                        # 运行单元测试
```

## 分支模型

- `main`：始终可发布，受保护，仅通过 PR 合入。
- `develop`：集成分支，功能先合到这里。
- `feature/<任务ID>-<简述>`：功能分支，从 `develop` 切出。

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/zh-huns/)：

- `feat:` 新功能
- `fix:` 缺陷修复
- `docs:` 文档
- `test:` 测试
- `refactor:` 重构
- `chore:` 工程杂项

## PR 要求

1. 关联任务编号（如 T-07），说明改动范围与验证方式。
2. `ruff check src tests` 与 `pytest` 全部通过。
3. 涉及 UI 的改动需附截图或 GIF。
4. 不引入与 PR 目标无关的改动；新增依赖需在 PR 描述中说明理由。
5. 代码注释与文档使用简体中文，标识符使用英文。

## 行为准则

互相尊重、就事论事。任何形式的骚扰、人身攻击都不被接受。

## 版权与许可

提交即表示你同意你的贡献以 MIT 许可证发布。
