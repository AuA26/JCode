# JCode

> 本地模型也能用的 Coding Agent。小模型做小事，大模型做大事。

## v0.1.1

| 特性 | 说明 |
|------|------|
| 多步流水线 | LLM 拆分复合请求（写代码+加注释），自动排序执行 |
| 程序化删注释 | nocomment 专家用 tokenize 剥离注释，零 API 调用 |
| 文件追踪 | 跨轮记住写入路径，无目录指令也能找到目标文件 |
| TUI 简化 | 转圈动画代替刷屏，非对话路由只显示写入路径 |
| 路由日志 | ROU_TN/ 目录记录每次分类结果，供训练分析 |

---

## 设计哲学

LLM 只做一件事 —— **生成代码**。路由、定位、验证全部走确定性逻辑，ms 级响应，零幻觉。

```
你说 "修复登录失败"
   │
   ├─ Gate     → 关键词 + AI 混合路由 (0.7 / 0.3)
   ├─ Locator  → 关键词 + AST 调用图，ms 级定位
   ├─ Generate → LLM 只改目标函数
   └─ Verify   → 语法检查 + pytest，断言失败重试 1 次
```

---

## 快速开始

```bash
pip install git+https://github.com/AuA26/JCode.git
jcode
```

首次启动自动进入 **TUI 配置向导**（↑↓ 选择，Enter 确认，ESC 回退）：

```
╔══════════════════════════════════════════════════╗
║      ██╗ ██████╗ ██████╗ ██████╗ ███████╗        ║
║      ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝        ║
║      ██║██║     ██║   ██║██║  ██║█████╗          ║
║ ██   ██║██║     ██║   ██║██║  ██║██╔══╝          ║
║ ╚█████╔╝╚██████╗╚██████╔╝██████╔╝███████╗        ║
║  ╚════╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝        ║
║                                                  ║
║           Coding Agent  v0.1.0                   ║
║         github.com/AuA26/JCode                   ║
╚══════════════════════════════════════════════════╝
```

### 支持的后端

| Provider | 说明 |
|----------|------|
| Ollama 本地 | 自动检测服务，支持下载模型，一键启动 |
| Ollama 远程 | 连接其他设备的 Ollama 服务 |
| DeepSeek | 云端 API，deepseek-v4-pro / v4-flash |

### Ollama 本地部署

自动检测 Ollama 运行状态 → 列出已安装模型 → 无模型时引导下载：

| 系列 | 参数量 |
|------|--------|
| gemma4 | e4b / 26b / 31b |
| qwen3.5 | 9b / 27b / 35b |
| qwen3.6 | 27b / 35b |
| deepseek-r1 | 14b / 32b |

```
下载 gemma4:e4b...
  [███████████████████████████████████████████████░] 98.3%
✓ 下载完成
```

---

## 使用

```bash
jcode
```

直接输入自然语言：

```
> 修复 auth.py 登录报错
> 写一个 FastAPI 用户注册接口
> 给 utils.py 的函数加上类型注解
> Django 怎么连 MySQL
```

### 流水线

| 路由 | 流水线 | 触发词 |
|------|--------|--------|
| bugfix | Locator → Generator → Verifier | 修复/fix/bug/报错/error |
| codegen | Generator → Verifier | 写/创建/实现/generate |
| refactor | Locator → Generator → Verifier | 重构/优化/refactor |
| test | Generator → Verifier | 测试/test/pytest |
| explain | Chat | 解释/分析/explain |
| chat | Chat | 默认 |

### 命令

```
/help              帮助
/api show          查看配置
/api set           重新配置
/model <name>      切换模型
/experts           列出专家
/plan <任务>       显示执行计划
/cd <路径>         切换目录
/files             列出文件
/exit              退出
```

---

## 安装

### 环境要求

- Python 3.10+

### 安装 JCode

```bash
pip install git+https://github.com/AuA26/JCode.git
```

安装后运行 `jcode` 启动。

或本地开发：

```bash
git clone https://github.com/AuA26/JCode.git
cd JCode
pip install -e .
```

### 可选依赖

如需 Ollama 模型下载功能（进度条 + 自动拉取）：

```bash
pip install ollama
```

核心依赖（httpx、pyyaml、prompt-toolkit）会在安装 JCode 时自动安装。

---

## 项目结构

```
JCode/
├── main.py                CLI 入口
├── main_code/
│   ├── config.py          配置管理 + TUI 向导
│   ├── gate.py            关键词+AI 混合路由
│   ├── locator.py         关键词 + AST 代码定位
│   ├── generator.py       LLM 代码生成
│   ├── verifier.py        语法检查 + pytest
│   ├── pipeline.py        流水线调度
│   ├── commands.py        REPL 命令系统
│   ├── llm.py             LLM 后端 (Ollama/DeepSeek)
│   ├── tools.py           文件读写、命令执行
│   ├── context.py         对话上下文管理
│   ├── tui.py             零依赖键盘导航
│   ├── banner.py          ANSI 标题渲染
│   ├── version.py         版本管理
│   └── net_set.py         网络检测
├── experts/               内置专家 (BugFix/FastAPI/MySQL/TypeHint/Docstring)
└── tests/                 测试套件
```

---

## License

Apache License V2
