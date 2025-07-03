# 贡献指南

感谢您考虑为Girdbot_hedge项目做出贡献！以下是一些帮助您开始的指南。

## 开发流程

1. Fork项目仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开Pull Request

## 代码规范

- 遵循PEP 8 Python代码风格指南
- 使用有意义的变量名和函数名
- 为所有函数和类添加文档字符串
- 保持代码简洁和模块化
- 新增功能必须包含测试

## 提交PR前的检查清单

- [ ] 代码遵循项目的代码风格
- [ ] 所有测试都通过
- [ ] 更新了相关文档
- [ ] 添加了适当的测试用例
- [ ] PR标题清晰地描述了更改内容

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/girdbot_hedge.git
cd girdbot_hedge

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows上使用: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install pytest flake8
```

## 测试

在提交PR之前，请确保运行测试并确保它们通过：

```bash
pytest
```

## 问题和功能请求

使用GitHub Issues跟踪问题和功能请求。提交问题时，请尽可能详细地描述问题或功能请求。

## 许可证

通过贡献您的代码，您同意您的贡献将根据项目的MIT许可证进行许可。 