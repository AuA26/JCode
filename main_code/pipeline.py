from __future__ import annotations
import os
import re
import json
from pathlib import Path
from .gate import RouteResult
from .locator import locate
from .generator import generate
from .verifier import verify
from .context import Context
from .tools import write_file
from .llm import chat
from . import config as cfg_mod

GREEN = "\033[32m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _detect_user_dir() -> str:
    return str(Path.home()).replace("\\", "/")


_USER_DIR = _detect_user_dir()

_INTENT_PROMPT = """Analyze this request. Return ONLY a JSON object:
{"task": "the coding task description", "path": "full absolute output file path"}

Path rules (USE FORWARD SLASHES):
- User folder is: """ + _USER_DIR + """
- Desktop is: """ + _USER_DIR + """/Desktop
- Downloads: """ + _USER_DIR + """/Downloads
- "桌面" -> """ + _USER_DIR + """/Desktop/filename.py
- "用户文件夹" or "用户目录" -> """ + _USER_DIR + """/filename.py
- "C盘" -> C:/
- No location -> """ + _USER_DIR + """/filename.py
- Always include .py extension
- Generate suitable filename from task

Request: """

_DEST_KEYWORDS = {
    "desktop": _USER_DIR + "/Desktop",
    "桌面": _USER_DIR + "/Desktop",
    "下载": _USER_DIR + "/Downloads",
    "downloads": _USER_DIR + "/Downloads",
}


def _parse_dest_dir(query: str) -> Path | None:
    for kw, folder in _DEST_KEYWORDS.items():
        if kw in query.lower():
            return Path(folder)
    m = re.search(r"(?:到|保存|写入|输出)[:：]?\s*([A-Za-z]:[^\s,，]+)", query)
    if m:
        p = Path(m.group(1))
        return p if p.is_absolute() else None
    if "用户文件夹" in query or "用户目录" in query or "c盘用户" in query.lower():
        sub = re.search(r"(?:子目录|文件夹|目录|里面)\s*(\w+)", query)
        if sub:
            p = Path(_USER_DIR) / sub.group(1)
            if p.exists():
                return p
        return Path(_USER_DIR)
    return None


def _analyze_intent(query: str, cfg: "cfg_mod.Config") -> dict:
    try:
        raw = chat(
            messages=[{"role": "user", "content": _INTENT_PROMPT + query}],
            cfg=cfg, temperature=0.0, max_tokens=300,
        )
        raw = raw.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:]
        data = json.loads(raw)
        path = data.get("path", "").replace("\\", "/")
        return {"task": data.get("task", query), "path": path}
    except Exception:
        dest = _parse_dest_dir(query)
        if dest:
            filename = _guess_filename(query)
            return {"task": query, "path": str((dest / filename).resolve()).replace("\\", "/")}
        return {"task": query, "path": ""}


def _guess_filename(query: str) -> str:
    m = re.search(r"(?:写|创建|生成).*?([a-zA-Z_][\w]*)\s*(?:代码|程序|脚本)?", query)
    if m:
        return m.group(1) + ".py"
    eng = {"贪吃蛇": "snake_game", "snake": "snake_game", "俄罗斯方块": "tetris", "扫雷": "minesweeper", "爬虫": "spider"}
    for kw, name in eng.items():
        if kw in query.lower():
            return name + ".py"
    return "output.py"


def run_pipeline(
    query: str,
    route: RouteResult,
    project_dir: Path,
    cfg: "cfg_mod.Config",
    ctx: Context,
) -> str:
    context_info = ""
    matches = []
    intent = _analyze_intent(query, cfg) if route.route in ("codegen", "test") else {"task": query, "path": ""}
    effective_query = intent.get("task", query)
    dest_path = intent.get("path", "")

    if "locator" in route.pipeline:
        matches = locate(query, project_dir)
        if matches:
            lines = ["relevant:"]
            for m in matches[:5]:
                loc = f"# {m.filepath}"
                if m.function_name:
                    loc += f" -> {m.function_name}() (L{m.line_start}-L{m.line_end})"
                lines.append(loc)
                if m.snippet:
                    lines.append(m.snippet[:300])
                    lines.append("---")
            context_info = "\n".join(lines)
            ctx.set_files([m.filepath for m in matches])
            print(f"  locate: {len(matches)} matches")
        else:
            print("  locate: no matches")

    print(f"  generate... ({cfg.model})")
    if route.expert:
        print(f"  expert: {route.expert}")
    if dest_path:
        print(f"  output: {CYAN}{dest_path}{RESET}")
    result = generate(route, effective_query, context_info, cfg)

    if result.explanation:
        print(f"\n  {result.explanation[:200]}")

    if result.code:
        print(f"\n{'─' * 60}")
        print(result.code[:800])
        if len(result.code) > 800:
            print(f"\n  ... ({len(result.code)} chars)")
        print(f"{'─' * 60}")

    if "verifier" in route.pipeline:
        filepath = dest_path or result.filepath or (str(matches[0].filepath) if matches else None)
        if not filepath and result.code and route.route in ("codegen", "test"):
            dest_dir = _parse_dest_dir(query) or project_dir
            filename = _guess_filename(query)
            filepath = str(dest_dir / filename)
        if not filepath:
            filepath = None
        elif filepath and not Path(filepath).is_absolute():
            filepath = str(project_dir / filepath)

        print(f"\n  验证...")
        run_tests = bool(matches) and route.route in ("bugfix", "refactor")
        vresult = verify(result.code, filepath, project_dir, run_tests=run_tests)

        if vresult.ok:
            print("  语法 OK")
            if filepath and result.code:
                try:
                    write_file(filepath, result.code)
                    abs_path = str(Path(filepath).resolve())
                    print(f"  {GREEN}已写入: {abs_path}{RESET}")
                except Exception as e:
                    print(f"  写入失败: {e}")
        else:
            for err in vresult.errors:
                print(f"  失败 {err[:200]}")

            if vresult.error_category == "assertion":
                print("  重试...")
                retry_query = f"修复测试失败:\n{vresult.errors[0]}"
                retry_result = generate(route, retry_query, context_info, cfg)
                vresult2 = verify(retry_result.code, filepath, project_dir, run_tests=run_tests)
                if vresult2.ok:
                    print("  重试成功")
                    if filepath:
                        write_file(filepath, retry_result.code)

    return result.code or result.raw_response
