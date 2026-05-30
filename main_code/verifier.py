from __future__ import annotations
import ast
import logging
from pathlib import Path
from dataclasses import dataclass, field
from .tools import run_cmd, write_file

logger = logging.getLogger("jcode.verifier")


@dataclass
class VerifyResult:
    ok: bool
    syntax_ok: bool
    tests_ok: bool
    errors: list[str] = field(default_factory=list)
    error_category: str = ""
    test_output: str = ""


def _check_syntax(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"syntax error: L{e.lineno} {e.msg}"


def _classify_error(error_text: str) -> str:
    if "SyntaxError" in error_text or "IndentationError" in error_text:
        return "syntax"
    if "AssertionError" in error_text or "assert" in error_text.lower():
        return "assertion"
    if "ImportError" in error_text or "ModuleNotFoundError" in error_text:
        return "import"
    return "runtime"


def verify(
    code: str,
    filepath: str | Path | None = None,
    project_dir: str | Path | None = None,
    run_tests: bool = True,
) -> VerifyResult:
    result = VerifyResult(ok=True, syntax_ok=True, tests_ok=True)

    syntax_ok, syntax_error = _check_syntax(code)
    if not syntax_ok:
        result.syntax_ok = False
        result.ok = False
        result.errors.append(syntax_error)
        result.error_category = "syntax"
        return result

    if filepath and code:
        try:
            fp = Path(filepath)
            write_file(fp, code)
            logger.info(f"wrote: {fp}")
        except Exception as e:
            result.errors.append(f"write failed: {e}")
            result.ok = False
            result.error_category = "runtime"
            return result

    if project_dir and run_tests:
        pj = Path(project_dir)
        test_dir = pj / "tests"
        if test_dir.exists() and list(test_dir.glob("test_*.py")):
            r = run_cmd("python -m pytest tests/ -v --tb=short", cwd=pj, timeout=60)
            result.test_output = f"{r.stdout}\n{r.stderr}"
            if not r.ok and r.returncode != 5:
                result.tests_ok = False
                result.ok = False
                result.error_category = _classify_error(r.stderr or r.stdout)
                result.errors.append(f"test failed:\n{r.stderr[:500] or r.stdout[:500]}")

    return result


def collapse_retry(result: VerifyResult, retries: int) -> bool:
    if result.ok:
        return False
    if result.error_category == "assertion" and retries < 1:
        return True
    return False
