from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .gate import RouteResult
from .llm import chat

_EXPERT_DIR = Path(__file__).parent.parent / "experts"
_EXPERT_CACHE: dict[str, str] = {}


@dataclass
class GeneratedCode:
    code: str
    filepath: str = ""
    explanation: str = ""
    raw_response: str = ""


_BUGFIX_PROMPT = """You are a bug fix expert.
Rules:
1. Only fix the specified bug, do not modify other code
2. Return the complete fixed file with ```python
3. First explain the root cause, then give the fix
4. Keep original code style and indentation"""

_CODEGEN_PROMPT = """You are a Python developer.
Rules:
1. Start response with "file: filename.py" to specify output file
2. Generate clean Python code based on requirements
3. Return complete code with ```python
4. Include type annotations and docstrings
5. Handle edge cases and errors"""

_REFACTOR_PROMPT = """You are a refactoring expert.
Rules:
1. Improve structure without changing external behavior
2. Return complete refactored file with ```python
3. Keep type annotations intact
4. Explain what was refactored, then give the code"""

_TEST_PROMPT = """You are a test engineer.
Rules:
1. Write pytest tests
2. Cover normal, edge, and error cases
3. Return complete test code with ```python"""

_EXPLAIN_PROMPT = """You are a Python code analyst. Explain the code clearly in Chinese."""

_CHAT_PROMPT = """You are a programming assistant. Reply in Chinese with practical advice."""


_PROMPTS = {
    "bugfix": _BUGFIX_PROMPT,
    "codegen": _CODEGEN_PROMPT,
    "refactor": _REFACTOR_PROMPT,
    "test": _TEST_PROMPT,
    "explain": _EXPLAIN_PROMPT,
    "chat": _CHAT_PROMPT,
}


def _load_expert(name: str) -> str | None:
    if name in _EXPERT_CACHE:
        return _EXPERT_CACHE[name]
    path = _EXPERT_DIR / f"{name}.md"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    prompt = "\n".join(lines).strip()
    _EXPERT_CACHE[name] = prompt
    return prompt


def generate(
    route: RouteResult,
    query: str,
    context_info: str,
    cfg,
) -> GeneratedCode:
    system_prompt = _PROMPTS.get(route.route, _CHAT_PROMPT)
    if route.expert:
        expert_prompt = _load_expert(route.expert)
        if expert_prompt:
            system_prompt = expert_prompt

    user_message = query
    if context_info:
        user_message = f"context:\n{context_info}\n\n---\n\nrequest: {query}"

    messages = [{"role": "user", "content": user_message}]

    raw = chat(messages=messages, cfg=cfg, system_prompt=system_prompt)

    code = ""
    filepath = ""
    explanation = ""

    import re
    code_blocks = re.findall(r'```(?:python|py)?\s*\n?(.*?)```', raw, re.DOTALL)

    if code_blocks:
        code = "\n\n".join(code_blocks)

    path_match = re.search(r'(?:file|path)[:：]\s*([^\s\n]+\.py)', raw)
    if path_match:
        filepath = path_match.group(1)

    if code_blocks:
        first_block_start = raw.find("```")
        if first_block_start > 0:
            explanation = raw[:first_block_start].strip()

    return GeneratedCode(
        code=code or raw,
        filepath=filepath,
        explanation=explanation,
        raw_response=raw,
    )
