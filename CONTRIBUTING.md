# JCode 贡献指南

## 快速开始

```bash
git clone https://github.com/AuA26/JCode.git
cd JCode
pip install httpx pyyaml
python main.py
```

## PR 要求

### 必须满足

1. **测试全绿**
   ```bash
   python -m pytest tests/ -v
   ```

2. **新模块必须有测试**
   - 新增 `main_code/xxx.py` → `tests/test_xxx.py`
   - 改已有模块 → 补充对应测试

3. **不超过 200 行**
   每个新文件不超过 200 行。超过请拆分。

4. **类型注解**
   函数签名必须写参数类型和返回类型：
   ```python
   def classify(text: str) -> Route:
   ```

### 不接受

- 引入需要云服务的依赖
- 引入向量数据库（Chroma、Pinecone 等）
- 在模块里加 `print()` 调试（用 `logging`）
- 改动其他模块的全局变量

## PR 模板

```markdown
## 改动内容
（一句话说明做了什么）

## 改动类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 性能优化
- [ ] 文档

## 测试
- [ ] 现有测试全部通过
- [ ] 新增了测试

## 新增依赖
| 包名 | 用途 | 离线可用 |
|------|------|---------|
|      |      |         |
```

## 代码风格

- Python 3.10+，类型注解完整
- 用 `"""docstring"""` 写函数说明
- 异常处理必须打 `logging.warning/debug`
- 模块顶部标注 `# PUBLIC:` 列出对外接口
