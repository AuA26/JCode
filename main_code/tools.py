from __future__ import annotations
import sys
import subprocess
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("jcode.tools")


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def read_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {p}")
    return p.read_text(encoding="utf-8")


def write_file(path: str | Path, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info(f"wrote: {p}")


def list_files(directory: str | Path, pattern: str = "*.py") -> list[Path]:
    p = Path(directory)
    if not p.exists():
        return []
    exclude_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".deep-copilot"}
    return sorted(
        f for f in p.rglob(pattern)
        if not any(ex in f.parts for ex in exclude_dirs)
    )


def run_cmd(cmd: str, cwd: str | Path | None = None, timeout: int = 30) -> CmdResult:
    try:
        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "cwd": str(cwd) if cwd else None,
            "timeout": timeout,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        result = subprocess.run(cmd, shell=True, **kwargs)
        return CmdResult(
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"timeout ({timeout}s): {cmd[:100]}")
        return CmdResult(returncode=-1, stdout="", stderr="timeout", timed_out=True)
    except Exception as e:
        logger.warning(f"cmd failed: {e}")
        return CmdResult(returncode=-1, stdout="", stderr=str(e))
