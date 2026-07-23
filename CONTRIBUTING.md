# 贡献指南

感谢你对 NexusFlow 的关注！欢迎贡献。

## 开发环境搭建

```bash
git clone https://github.com/tsingxuanhan/NexusFlow.git
cd NexusFlow
pip install -r requirements.txt
cp .env.example .env  # 填入 API Key
python run.py
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档变更 |
| `refactor` | 重构（不改变功能） |
| `chore` | 构建/工具/杂项 |
| `benchmark` | 实验数据 |

示例：`feat(cognition): add perspective decomposition strategy #6`

## 代码风格

- Python 3.10+
- 使用类型注解（`def func(x: int) -> str:`）
- 新增模块需附带单元测试（`tests/` 目录）
- 运行测试：`python -m pytest tests/ -v`

## 提交前检查

- [ ] 测试通过：`python -m pytest tests/`
- [ ] 无硬编码密钥（CI 会自动扫描 gitleaks）
- [ ] 文档已更新（如有功能变更）
- [ ] CHANGELOG.md 已更新（如有版本发布）

## 安全

- **严禁**在代码中硬编码 API Key，统一使用环境变量
- 参考 [SECURITY.md](SECURITY.md)

## 许可证

提交代码即表示同意以 MIT 许可证授权贡献内容。
