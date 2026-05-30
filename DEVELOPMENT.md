# JCode 开发文档

## 项目结构

```
JCode/
├── main.py                CLI 入口 + REPL 循环
├── main_code/
│   ├── __init__.py
│   ├── config.py          配置管理 + TUI 向导 (Ollama/DeepSeek)
│   ├── gate.py            关键词 + AI 混合路由
│   ├── locator.py         关键词 + AST 代码定位
│   ├── generator.py       LLM 代码生成
│   ├── verifier.py        语法检查 + pytest 验证
│   ├── pipeline.py        流水线调度
│   ├── commands.py        REPL 命令系统
│   ├── llm.py             LLM 后端 (Ollama 原生 / DeepSeek OpenAI)
│   ├── tools.py           文件读写、命令执行
│   ├── context.py         对话上下文管理
│   ├── tui.py             零依赖键盘导航
│   ├── banner.py          ANSI 标题渲染
│   ├── version.py         版本管理
│   ├── net_set.py         网络检测
│   └── Version.json       版本元数据
├── experts/               内置专家 (BugFix/FastAPI/MySQL/TypeHint/Docstring)
├── tests/
│   └── test_core.py       核心模块测试
├── pyproject.toml         包配置
├── README.md
├── CONTRIBUTING.md
└── DEVELOPMENT.md
```

---

## 设计原则

1. **每个文件 ≤ 200 行**。超过就拆。
2. **LLM 只做生成**。路由、定位、验证全部走确定性逻辑。
3. **零魔法**。不搞动态导入、不搞元编程、不搞注册表。
4. **函数有返回值**。不靠全局变量传递状态。
5. **异常不裸吞**。所有 `except Exception` 必须打日志。
6. **函数名用英文**，禁止拼音和乱写。
7. **全类型注解**，Python 3.10+ 语法。

---

## 模块接口约定

通过类型注解声明接口，不依赖注释：

```python
def classify(user_input: str, llm_classify: Callable | None = None) -> RouteResult:
    ...
```

导入使用包路径（不借助 `sys.path` hack）：

```python
from main_code.gate import classify
```

---

## 依赖管理

核心依赖（自动安装）：
- `httpx>=0.25` — HTTP 请求 + 流式下载
- `pyyaml>=6.0` — 配置读写

可选依赖：
- `ollama>=0.4` — Ollama 模型下载（进度条 + 自动拉取）

安装全部：
```bash
pip install httpx pyyaml ollama
```

---

## 运行

```bash
python main.py
```

或安装后使用 CLI：

```bash
pip install -e .
jcode
```

---

## 测试

```bash
python -m pytest tests/ -v
```

---

## 打包发布

```bash
python -m build
twine upload dist/*
```

---

## 版本号

唯一真相源：`main_code/Version.json` 中的 `version` 字段。
发版时改这一个地方即可。
