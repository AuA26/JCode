from __future__ import annotations
from pathlib import Path
from .config import Config, init_config, save_config
from .context import Context
from .gate import classify, RouteResult
from .locator import locate
from .llm import classify as llm_classify
from .tools import list_files

# PUBLIC: HELP_TEXT, COMMAND_DESCRIPTIONS, EXPERTS_INFO, handle_command

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "help": "获取帮助",
    "exit": "退出",
    "api": "API配置",
    "model": "切换模型",
    "experts": "内置专家",
    "plan": "执行计划",
    "cd": "切换目录",
    "files": "项目文件",
}

HELP_TEXT = """
JCode 命令:
  /help              获取帮助
  /exit              退出程序
  /api show          查看 API 配置
  /api set           重新配置 API
  /model <名称>      切换模型
  /experts           列出内置专家
  /plan <任务>       显示执行计划
  /cd <路径>         切换工作目录
  /files             列出项目文件

  直接输入需求即可:
    > 修复 auth.py 登录报错
    > 写一个 FastAPI 用户注册接口
    > 给 utils.py 加上类型注解
"""

EXPERTS_INFO = {
    "BugFix":    "fix/bug/error -> locate, generate, verify",
    "FastAPI":   "fastapi/route/endpoint -> inject api spec",
    "MySQL":     "mysql/table/index -> inject db spec",
    "TypeHint":  "type hint -> add annotations only",
    "Docstring": "docstring -> add docs only",
}


def handle_command(
    cmd: str,
    args: str,
    args2: str,
    cfg: Config,
    ctx: Context,
    project_dir: Path,
) -> tuple[bool, Config, Path]:
    if cmd == "/exit":
        print("  bye")
        return True, cfg, project_dir

    elif cmd == "/help":
        print(HELP_TEXT)

    elif cmd == "/api":
        if args == "show":
            masked = "***" + cfg.api_key[-4:] if len(cfg.api_key) > 4 else "(none)"
            print(f"\n  provider: {cfg.provider}\n  url: {cfg.base_url}\n  model: {cfg.model}\n  key: {masked}\n")
        elif args == "set":
            from .config import CONFIG_PATH
            if CONFIG_PATH.exists():
                CONFIG_PATH.unlink()
            cfg = init_config()

    elif cmd == "/model":
        if args:
            cfg.model = args
            save_config(cfg)
            print(f"\n  model: {args}\n")

    elif cmd == "/experts":
        print("\n  experts:")
        for name, desc in EXPERTS_INFO.items():
            print(f"    {name:<12} {desc}")
        print()

    elif cmd == "/plan":
        if args:
            print(f"\n  plan: {args[:60]}...\n")
            def llm_fn(text, labels):
                return llm_classify(text, labels, cfg)
            route = classify(args, llm_fn)
            print(f"  route: {route.route} ({route.confidence:.0%}, {route.source})")
            print(f"  pipeline: {' -> '.join(route.pipeline)}")
            if "locator" in route.pipeline:
                matches = locate(args, project_dir)
                if matches:
                    print(f"\n  found {len(matches)} matches:")
                    for m in matches[:5]:
                        loc = m.filepath.name
                        if m.function_name:
                            loc += f"::{m.function_name}()"
                        print(f"      {loc} ({m.relevance:.0%})")
                else:
                    print("  no matches")
            print()

    elif cmd == "/cd":
        if args:
            new_dir = Path(args).resolve()
            if new_dir.is_dir():
                project_dir = new_dir
                print(f"\n  cd: {project_dir}\n")
            else:
                print(f"  not found: {args}")

    elif cmd == "/files":
        py_files = list_files(project_dir)
        print(f"\n  {project_dir} ({len(py_files)} files)")
        for f in py_files[:20]:
            print(f"    {f.relative_to(project_dir)}")
        if len(py_files) > 20:
            print(f"    ... +{len(py_files) - 20}")
        print()

    else:
        print(f"  unknown: {cmd}")

    return False, cfg, project_dir
