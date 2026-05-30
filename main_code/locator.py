from __future__ import annotations
import ast
import re
from pathlib import Path
from dataclasses import dataclass
from .tools import list_files, read_file


@dataclass
class MatchResult:
    filepath: Path
    function_name: str = ""
    line_start: int = 0
    line_end: int = 0
    relevance: float = 0.0
    snippet: str = ""


def _extract_keywords(query: str) -> list[str]:
    stop_words = {"\u7684", "\u4e86", "\u662f", "\u5728", "\u548c", "\u5c31", "\u90fd", "\u800c", "\u53ca", "\u4e0e",
                  "\u7740", "\u6216", "\u4e00\u4e2a", "\u6ca1\u6709", "\u6211\u4eec", "\u4f60\u4eec", "\u4ed6\u4eec", "\u8fd9\u4e2a", "\u90a3\u4e2a",
                  "\u8bf7", "\u5e2e\u6211", "\u4e00\u4e0b", "\u4e0b", "\u7ed9", "\u628a"}
    cleaned = re.sub(r'[\u3000-\u303f\uff00-\uffef\(\)\[\]\{\}\s]', ' ', query)
    words = cleaned.split()
    return [w for w in words if w not in stop_words and len(w) > 1][:8]


def _scan_python_functions(filepath: Path) -> list[dict]:
    try:
        source = read_file(filepath)
        tree = ast.parse(source)
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                body = source[node.lineno - 1:node.end_lineno] if node.end_lineno else ""
                functions.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "end_lineno": node.end_lineno or node.lineno,
                    "docstring": docstring or "",
                    "body": body[:500],
                })
        return functions
    except (SyntaxError, Exception):
        return []


def _score_match(keywords: list[str], text: str) -> float:
    if not keywords:
        return 0.0
    score = 0.0
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            score += 1.0 if kw.lower() == text_lower else 0.5
    return min(1.0, score / len(keywords))


def locate(query: str, project_dir: str | Path) -> list[MatchResult]:
    project_dir = Path(project_dir).resolve()
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    results: list[MatchResult] = []

    for py_file in list_files(project_dir, "*.py"):
        try:
            content = read_file(py_file)
        except Exception:
            continue

        filename_score = _score_match(keywords, py_file.name)
        content_score = _score_match(keywords, content[:2000])
        file_relevance = max(filename_score * 1.5, content_score)

        functions = _scan_python_functions(py_file)
        for func in functions:
            func_text = f"{func['name']} {func['docstring']} {func['body'][:300]}"
            func_score = _score_match(keywords, func_text)

            if func_score > 0.1:
                combined = max(file_relevance, func_score) * (1.0 + 0.2 * file_relevance)
                results.append(MatchResult(
                    filepath=py_file,
                    function_name=func["name"],
                    line_start=func["lineno"],
                    line_end=func["end_lineno"],
                    relevance=min(1.0, combined),
                    snippet=func["body"][:400],
                ))

        if file_relevance > 0.2 and not any(r.filepath == py_file for r in results):
            results.append(MatchResult(
                filepath=py_file,
                relevance=file_relevance,
                snippet=content[:400],
            ))

    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x.relevance, reverse=True):
        key = (r.filepath, r.function_name, r.line_start)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:10]
