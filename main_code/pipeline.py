from __future__ import annotations
import os
import re
import json
import sys
import time
import threading
from pathlib import Path
from .gate import RouteResult
from .locator import locate
from .generator import generate, GeneratedCode
from .verifier import verify
from .context import Context
from .tools import write_file
from .llm import chat
from . import config as cfg_mod

GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

_SPINNER_CHARS = "|/-\\"


class Spinner:
    def __init__(self, msg: str = "正在生成"):
        self._msg = msg
        self._stop = threading.Event()

    def __enter__(self):
        self._t = threading.Thread(target=self._spin, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._t.join(timeout=0.3)
        sys.stdout.write("\r" + " " * (len(self._msg) + 4) + "\r")
        sys.stdout.flush()

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {self._msg} {_SPINNER_CHARS[i]}")
            sys.stdout.flush()
            i = (i + 1) % 4
            time.sleep(0.1)


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


def _looks_like_python(text: str) -> bool:
    import re
    py_patterns = [
        r'\bdef\s+\w+\s*\(', r'\bclass\s+\w+', r'\bimport\s+\w+',
        r'\bfrom\s+\w+\s+import', r'\bif\s+__name__', r'\breturn\b',
        r'\bprint\(', r'^\s*#', r'"""', r"'''", r'\w+\s*=\s*',
    ]
    for p in py_patterns:
        if re.search(p, text, re.MULTILINE):
            return True
    return False


def _strip_comments_programmatic(source: str) -> str:
    import tokenize
    import io
    result: list[str] = []
    last_row, last_col = 1, 0
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for tok in tokens:
        if tok.type in (tokenize.COMMENT, tokenize.NL):
            continue
        srow, scol = tok.start
        if srow > last_row:
            result.append("\n" * (srow - last_row))
            last_col = 0
        if scol > last_col:
            result.append(" " * (scol - last_col))
        result.append(tok.string)
        last_row, last_col = tok.end
    text = "".join(result)
    lines = text.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if non_empty:
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines) + "\n"


def run_pipeline(
    query: str,
    routes: list[RouteResult],
    project_dir: Path,
    cfg: "cfg_mod.Config",
    ctx: Context,
) -> str:
    last_output = ""
    last_code = ""
    last_filepath = ""
    total_routes = len(routes)
    for idx, route in enumerate(routes):
        label = route.route
        if route.expert:
            label += f"+{route.expert}"
        if total_routes > 1:
            print(f"\n  [{idx + 1}/{total_routes}] {label}")
        with Spinner():
            context_info = ""
            matches = []
            intent = _analyze_intent(query, cfg) if route.route in ("codegen", "test") else {"task": route.reasoning.split("task: ")[-1] if "task:" in route.reasoning else query, "path": ""}
            effective_query = intent.get("task", query)
            dest_path = intent.get("path", "")
            if last_code and route.route in ("explain", "refactor", "test"):
                context_info = f"previous generated code:\n```python\n{last_code}\n```"
                if last_filepath:
                    dest_path = last_filepath
            if last_output and not context_info and idx > 0:
                context_info = f"previous step output:\n{last_output[:1000]}"
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
            if not context_info and ctx.current_files:
                lines = ["previous file:"]
                for f in ctx.current_files[:5]:
                    try:
                        content = Path(f).read_text(encoding="utf-8")
                        lines.append(f"# {f}")
                        lines.append("```python")
                        lines.append(content[:2000])
                        lines.append("```")
                        if not dest_path:
                            dest_path = str(f)
                    except Exception:
                        lines.append(f"# {f} (unreadable)")
                context_info = "\n".join(lines)
            if route.expert == "nocomment" and context_info:
                import re as _re
                code_match = _re.search(r'```python\s*\n(.*?)```', context_info, _re.DOTALL)
                if code_match:
                    stripped = _strip_comments_programmatic(code_match.group(1))
                    result = GeneratedCode(code=stripped, explanation="程序化删除注释")
                else:
                    result = generate(route, effective_query, context_info, cfg)
            else:
                result = generate(route, effective_query, context_info, cfg)
        if result.code:
            last_code = result.code
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
            vresult = verify(result.code, filepath, project_dir, run_tests=bool(matches) and route.route in ("bugfix", "refactor"))
            if vresult.ok:
                if filepath and result.code:
                    try:
                        write_file(filepath, result.code)
                        abs_path = str(Path(filepath).resolve())
                        print(f"  {GREEN}已写入: {abs_path}{RESET}")
                        last_filepath = filepath
                        ctx.add_file(Path(filepath))
                    except Exception as e:
                        print(f"  {RED}写入失败: {e}{RESET}")
            else:
                for err in vresult.errors:
                    print(f"  {RED}错误 {err[:200]}{RESET}")
                if vresult.error_category == "assertion":
                    print("  retry...")
                    with Spinner("重试"):
                        retry_result = generate(route, f"修复测试失败:\n{vresult.errors[0]}", context_info, cfg)
                    vresult2 = verify(retry_result.code, filepath, project_dir, run_tests=bool(matches))
                    if vresult2.ok:
                        print("  retry OK")
                        if filepath:
                            write_file(filepath, retry_result.code)
                            last_filepath = filepath
                            last_code = retry_result.code
                            ctx.add_file(Path(filepath))
        elif result.code and dest_path:
            if not _looks_like_python(result.code):
                print(f"  {RED}跳过写入: 输出不含有效代码{RESET}")
                last_output = result.code or result.raw_response
                continue
            try:
                write_file(dest_path, result.code)
                abs_path = str(Path(dest_path).resolve())
                print(f"  {GREEN}已写入: {abs_path}{RESET}")
                last_filepath = dest_path
                ctx.add_file(Path(dest_path))
            except Exception as e:
                print(f"  {RED}写入失败: {e}{RESET}")
        last_output = result.code or result.raw_response
    return last_output
